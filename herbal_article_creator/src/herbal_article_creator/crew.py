import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from .tools.pubmed_tools import PubMedSearchTool, PubMedFetchTool, PubMedParseTool, PubMedSummaryTool
from .tools.tavily_tools import MyTavilySearchTool, ToolBudget
from .tools.rag_manager_tools import rag_manager
from .tools.fda_tools import search_fda_tool
from .tools.docx_tools import SaveMarkdownToDocxTool
from .tools.gdrive_upload_file_tools import gdrive_upload_file 
from .tools.sac_tools import search_SAC 
from .tools.browse_website_tools import browse_website_tool
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from .tools.pinecone_tools import (
    search_pinecone,
    search_pinecone_multiple
)
from string import Template

@CrewBase
class HerbalArticleCreator():
    """HerbalArticleCreator crew"""
    
    lang = os.getenv("OUTPUT_LANG", "en")
    agents_config = f"config/agents_production.yaml"
    tasks_config = f"config/tasks_production.yaml"
    
    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self, params=None):
        
        """
        Herbal Article Creator Crew
        Intelligent Agent System for Generating Thai Herbal Articles to support Modern Wellness Applications
        """
        self.params = params or {}
        self.rag_enabled = False
        self.herbal_context = ""
        self.shared = {}
        self.pubmed_search = PubMedSearchTool()
        self.pubmed_fetch = PubMedFetchTool()
        self.pubmed_parse = PubMedParseTool()
        self.pubmed_summary = PubMedSummaryTool()
        self.save_markdown_to_docx = SaveMarkdownToDocxTool()
        self.gdrive_upload_file = gdrive_upload_file
        self.search_SAC = search_SAC
        self.search_fda_tool = search_fda_tool
        self.browse_website_tool = browse_website_tool
        
        # Initialize Pinecone tools
        self._initialize_pinecone()
                                
        # Initialize RAG with error handling
        self._initialize_rag()
        
        print(f"\n{'='*70}")
        print("RAG Initialization Complete")
        print(f"{'='*70}")
        print(f"✓ Herbal context: {len(self.herbal_context):,} chars")
        print(f"  Citation format: {self.herbal_citation}")
        print(f"✓ Cultural context: {len(self.cultural_context):,} chars")
        print(f"  Citation format: {self.cultural_citation}")
        print(f"{'='*70}\n")
                
        self.research_budget = ToolBudget(
            max_calls=int(os.getenv("RESEARCH_MAX_CALLS", "6"))
        )
        
        self.serper_tool = MyTavilySearchTool(
            max_results=8, 
            search_depth="advanced"
        )
        self.serper_tool.name = "search_web"  
        self.serper_tool.description = "Search the web for general information about wellness trends and herbs"
        
        self.tavily_gwi = MyTavilySearchTool(
            include_domains=["globalwellnessinstitute.org"], 
            max_results=8
        )
        self.tavily_gwi.name = "search_wellness_institute"  
        self.tavily_gwi.description = "Search Global Wellness Institute website for authoritative wellness trends data"
        
        self.tavily_pmc = MyTavilySearchTool(
            include_domains=["pmc.ncbi.nlm.nih.gov"], 
            max_results=5, search_depth="advanced", 
            shared_budget=self.research_budget
        )
        self.tavily_pmc.name = "search_NCBI"  
        self.tavily_pmc.description = "Search NCBI"
                
        self.tavily_sac = MyTavilySearchTool(
            include_domains=["wikicommunity.sac.or.th"], 
            max_results=8
        )
        self.tavily_sac.name = "search_SAC" 
        self.tavily_sac.description = "Search Cultural Review for Herbal Article"

        # LLM configuration
        self.llm_mode = os.getenv("LLM_MODE", "global")
        self.llm = self._create_llm()
        self.llm_llama = self._create_llm_llama_3_3()
        self.llm_gpt = self._create_llm_gpt()
        self.llm_anthropic = self._create_llm_anthropic()
        self.llm_gemini = self._create_llm_gemini()

    def _initialize_pinecone(self):
        """Initialize Pinecone vector database"""
        try:
            if not os.getenv("PINECONE_API_KEY"):
                print("\nPinecone API key not found - skipping Pinecone initialization")
                self.pinecone_enabled = False
                self.pinecone_search = None
                self.pinecone_multi_search = None
                self.pinecone_context = ""
                self.pinecone_citation = "[source, p.X]"
                return
            
            print("\n🔍 Initializing Pinecone Vector Database...")
            
            self.pinecone_search = search_pinecone
            self.pinecone_multi_search = search_pinecone_multiple
        
            use_initial_context = os.getenv("PINECONE_BUILD_INITIAL_CONTEXT", "true").lower() == "true"
            
            if use_initial_context:
                initial_queries = os.getenv("HERBS_FOR_RESEARCH", "")
                if initial_queries:
                    print("Building initial Pinecone context via search_pinecone_multiple...")
                    try:
                        context = self.pinecone_multi_search.run(
                            initial_queries,
                            top_k=int(os.getenv("PINECONE_CONTEXT_TOP_K", "5")),
                            snippet_limit=int(os.getenv("PINECONE_SNIPPET_LIMIT", "240")),
                            total_limit=int(os.getenv("PINECONE_TOTAL_LIMIT", "8000")),
                        )
                        self.pinecone_context = context or ""
                        self.pinecone_citation = "[Pinecone:ID]"
                    except Exception as ie:
                        print(f"  pinecone_multi_search.run failed: {ie}")
                        self.pinecone_context = ""
                        self.pinecone_citation = "[Pinecone:ID]"
                else:
                    self.pinecone_context = ""
                    self.pinecone_citation = "[Pinecone:ID]"
            else:
                self.pinecone_context = ""
                self.pinecone_citation = "[Pinecone:ID]"
            
            self.pinecone_enabled = True
            print(" ✅ Pinecone initialized successfully")
                        
        except Exception as e:
            print(f"\nPinecone initialization failed: {e}")
            print("   Continuing without Pinecone...")
            self.pinecone_enabled = False
            self.pinecone_search = None
            self.pinecone_multi_search = None
            self.pinecone_context = ""
            self.pinecone_citation = "[source, p.X]"
        
    def _initialize_rag(self):
        """Initialize RAG with proper error handling"""
        try:            
            print("\n📚 Loading RAG contexts...")
            
            # Setup RAG for herbal documents
            print("  [1/2] Herbal documents (JSON + PDF)...")
            self.herbal_context, self.herbal_citation = rag_manager.setup_herbal_documents_combined()
            print(f"      ✓ Loaded {len(self.herbal_context):,} chars")
            
            # Setup RAG for cultural documents
            print("  [2/2] Cultural documents (JSON)...")
            self.cultural_context, self.cultural_citation = rag_manager.setup_cultural_documents_json_combined()
            print(f"      ✓ Loaded {len(self.cultural_context):,} chars")
            
            self.rag_enabled = True
            
            print("\n" + "="*70)
            print("✅ RAG Initialization Successful")
            print("="*70)
            print(f"✓ Herbal citation: {self.herbal_citation}")
            print(f"✓ Cultural citation: {self.cultural_citation}")
            
        except ImportError as e:
            print(f"\nWarning: Could not import rag_manager_tools: {e}")
            print("Continuing without RAG context...")
            self._set_rag_fallback()
            
        except FileNotFoundError as e:
            print(f"\nWarning: RAG data files not found: {e}")
            print("Continuing without RAG context...")
            self._set_rag_fallback()
            
        except Exception as e:
            print(f"\nWarning: RAG initialization failed: {e}")
            print("Continuing without RAG context...")
            import traceback
            traceback.print_exc()
            self._set_rag_fallback()
    
    def _set_rag_fallback(self):
        """Set fallback values when RAG fails"""
        self.herbal_context = ""
        self.cultural_context = ""
        self.herbal_citation = "[source, p.X]"
        self.cultural_citation = "[source, p.X]"
        self.rag_enabled = False
    
    def _create_llm(self):
        """Create and configure LLM instance"""
        model_name = os.getenv("LLM_MODEL_NAME", "llama")
        if model_name == "gpt":
            print(f"GLOBAL_LLM_MODEL: {model_name} - Creating GPT LLM")
            return LLM(
                model=os.getenv("LLM_GPT_MODEL", "gpt-4o-mini"),  
                api_key=os.getenv("OPENAI_API_KEY"), 
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
                top_p=float(os.getenv("LLM_TOP_P", "0.9")),
            )
        elif model_name == "gemini":  
            print(f"GLOBAL_LLM_MODEL: {model_name} - Creating Gemini LLM")
            return LLM(
                model=os.getenv("LLM_GEMINI_MODEL", "gemini/gemini-2.0-flash"),  
                api_key=os.getenv("GEMINI_API_KEY"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
            )
        elif model_name == "anthropic":
            print(f"GLOBAL_LLM_MODEL: {model_name} - Creating Anthropic LLM")
            return LLM(
                model=os.getenv("LLM_CLAUDE_MODEL", "claude-3-7-sonnet-latest"), 
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
                max_completion_tokens=int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "8000")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
                top_p=float(os.getenv("LLM_TOP_P", "0.9")),
            )   
        else:
            print(f"GLOBAL_LLM_MODEL: {model_name} - Creating Llama LLM")
            return LLM(
                model=os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct"),
                base_url=os.getenv("LLM_API_BASE", "https://integrate.api.nvidia.com/v1"),
                api_key=os.getenv("LLM_API_KEY"),
                custom_llm_provider=os.getenv("LLM_PROVIDER"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
                top_p=float(os.getenv("LLM_TOP_P", "0.9")),
            )
    
    def _create_llm_llama_3_1(self):
        """Create and configure LLM instance"""
        return LLM(
            model=os.getenv("LLM_LLAMA_MODEL", "meta/llama-3.1-8b-instruct"),
            base_url=os.getenv("LLM_API_BASE", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("NVIDIA_NIM_API_KEY"),
            custom_llm_provider="",
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
            
    def _create_llm_llama_3_3(self):
        """Create and configure LLM instance"""
        return LLM(
            model=os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct"),
            base_url=os.getenv("LLM_API_BASE", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("LLM_API_KEY"),
            custom_llm_provider=os.getenv("LLM_PROVIDER"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
        
    def _create_llm_gpt(self):
        """Create and configure LLM instance"""
        return LLM(
            model=os.getenv("LLM_GPT_MODEL", "gpt-4o-mini"), 
            api_key=os.getenv("OPENAI_API_KEY"), 
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
    
    def _create_llm_anthropic(self):
        """Create and configure LLM instance"""
        return LLM(
            model=os.getenv("LLM_CLAUDE_MODEL", "claude-3-7-sonnet-latest"), 
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
            max_completion_tokens=int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "8000")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
    
    def _create_llm_gemini(self):
        """Create and configure LLM instance"""
        return LLM(
            model=os.getenv("LLM_GEMINI_MODEL", "gemini/gemini-2.0-flash"), 
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.5")),
        )
        
    def _get_llm_for_agent(self, agent_key: str):
        """
        LLM: blind model provide to Agent
        """
        if self.llm_mode == "global":
            return self.llm
        
        elif self.llm_mode == "blind_group_B":
            if agent_key in [
                "trend_analyst_agent",
                "herbal_laboratory_agent",
                "research_agent",
                "compliance_checker_agent",
                "safety_inspector_agent",
                "clinical_toxicologist_agent",
                "cultural_editor_agent",
                "internal_knowledge_agent",
            ]:
                print(f"🧠 Assigning [GPT-4.1] to evaluate agent: {agent_key}")
                return self._create_llm_gpt()
            
            elif agent_key in [
                "qa_auditor_agent",
                "content_strategist_agent"         
            ]:
                print(f"🧠 Assigning [Gemini 2.0 flash] to research agent: {agent_key}")
                return self._create_llm_gemini()
                                    
            elif agent_key in [
                "planner_agent",
                "writer_agent",
                "formatter_agent"
            ]:
                print(f"🧠 Assigning [Claude 3.7] to research agent: {agent_key}")
                return self._create_llm_anthropic()

            else:
                print(f"🧠 Assigning [Llama 3.1-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_1()
            
        elif self.llm_mode == "blind_group_C":
            if agent_key in [
                "trend_analyst_agent",
                "herbal_laboratory_agent",
                "research_agent",
                "compliance_checker_agent",
                "safety_inspector_agent",
                "clinical_toxicologist_agent",
            ]:
                print(f"🧠 Assigning [Gemini 2.0 flash] to research agent: {agent_key}")
                return self._create_llm_gemini()
            
            elif agent_key in [
                "cultural_editor_agent",
                "internal_knowledge_agent",
                "qa_auditor_agent",
                "content_strategist_agent"         
            ]:
                print(f"🧠 Assigning [GPT-4.1] to evaluate agent: {agent_key}")
                return self._create_llm_gpt()
                                    
            elif agent_key in [
                "planner_agent",
                "writer_agent",
                "formatter_agent"
            ]:
                print(f"🧠 Assigning [Llama 3.3-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_3()

            else:
                print(f"🧠 Assigning [Llama 3.1-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_1()
            
        elif self.llm_mode == "blind_group_D":
            if agent_key in [
                "trend_analyst_agent",
                "herbal_laboratory_agent",
                "research_agent",
                "compliance_checker_agent",
                "safety_inspector_agent",
                "clinical_toxicologist_agent",
                "cultural_editor_agent",
                "internal_knowledge_agent",
            ]:
                print(f"🧠 Assigning [GPT-4.1] to research agent: {agent_key}")
                return self._create_llm_gpt()
            
            elif agent_key in [
                "qa_auditor_agent",
                "content_strategist_agent"         
            ]:
                print(f"🧠 Assigning [Gemini] to evaluate agent: {agent_key}")
                return self._create_llm_gemini()
                                    
            elif agent_key in [
                "planner_agent",
                "writer_agent",
                "formatter_agent"
            ]:
                print(f"🧠 Assigning [Llama 3.3-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_3()

            else:
                print(f"🧠 Assigning [Llama 3.1-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_1()
        
        elif self.llm_mode == "blind_group_E":
            if agent_key in [
                "qa_auditor_agent",
                "content_strategist_agent"         
            ]:
                print(f"🧠 Assigning [Gemini] to evaluate agent: {agent_key}")
                return self._create_llm_gemini()
            
            elif agent_key in [
                "planner_agent",
                "writer_agent",
                "formatter_agent"
            ]:
                print(f"🧠 Assigning [Claude 3.7] to research agent: {agent_key}")
                return self._create_llm_anthropic()
                                    
            else:
                print(f"🧠 Assigning [Llama 3.3-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_3()
        
        else:
            if agent_key in [
                "qa_auditor_agent",
                "content_strategist_agent"         
            ]:
                print(f"🧠 Assigning [Gemini] to evaluate agent: {agent_key}")
                return self._create_llm_gemini()
                                    
            elif agent_key in [
                "planner_agent",
                "writer_agent",
                "formatter_agent"
            ]:
                print(f"🧠 Assigning [Llama 3.3-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_3()

            else:
                print(f"🧠 Assigning [Llama 3.1-70B] to agent: {agent_key}")
                return self._create_llm_llama_3_1()
              
    @agent
    def trend_analyst_agent(self) -> Agent:
        """Trend Analyst"""
        agent_key = 'trend_analyst_agent'
        config = self.agents_config['trend_analyst_agent'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def herbal_laboratory_agent(self) -> Agent:
        """Herbal Laboratory Analyst"""
        agent_key = 'herbal_laboratory_agent'
        config = self.agents_config['herbal_laboratory_agent'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )

    @agent
    def research_agent(self) -> Agent:
        """Research Agent"""
        agent_key = 'research_agent'
        config = self.agents_config['research_agent'].copy()
        
        ctx = {"herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))}

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)
        
        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )

    @agent
    def compliance_checker_agent(self) -> Agent:
        """Compliance Checker"""
        agent_key = 'compliance_checker_agent'
        config = self.agents_config['compliance_checker_agent'].copy()
        
        ctx = {"herbs_thai": self.params.get("herbs_thai", os.getenv("HERBS_FOR_RESEARCH_THAI", ""))}

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)
                
        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def safety_inspector_agent(self) -> Agent:
        """Safety Inspector"""
        agent_key = 'safety_inspector_agent'
        config = self.agents_config['safety_inspector_agent'].copy()
        
        ctx = {"herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))}

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def clinical_toxicologist_agent(self) -> Agent:
        """clinical Toxicologist"""
        agent_key = 'clinical_toxicologist_agent'
        config = self.agents_config['clinical_toxicologist_agent'].copy()
        
        ctx = {"herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))}

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
            
    @agent
    def cultural_editor_agent(self) -> Agent:
        """Cultural Editor"""
        agent_key = 'cultural_editor_agent'
        config = self.agents_config['cultural_editor_agent'].copy()     

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))
           
        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def internal_knowledge_agent(self) -> Agent:
        """Internal knowledge"""
        agent_key = 'internal_knowledge_agent'
        config = self.agents_config['internal_knowledge_agent'].copy()
        
        ctx = {"herbs_thai": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH_THAI", ""))}

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def planner_agent(self) -> Agent:
        """Planner Agent"""
        agent_key = 'planner_agent'
        config = self.agents_config['planner_agent'].copy()
        
        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def writer_agent(self) -> Agent:
        """Writer Agent"""
        agent_key = 'writer_agent'
        config = self.agents_config['writer_agent'].copy()
        
        ctx = {
            "herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", "")),
            "lang": getattr(self, "lang", "en")
        }

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = Template(_as_str(config.get("goal"))).safe_substitute(**ctx)
        final_backstory = Template(_as_str(config.get("backstory"))).safe_substitute(**ctx)
                
        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def qa_auditor_agent(self) -> Agent:
        """QA Auditor Agent"""
        agent_key = 'qa_auditor_agent'
        config = self.agents_config['qa_auditor_agent'].copy()
        
        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @agent
    def content_strategist_agent(self) -> Agent:
        """Content Strategist Agent"""
        agent_key = 'content_strategist_agent'
        config = self.agents_config['content_strategist_agent'].copy()
        
        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_goal = _as_str(config.get("goal"))
        final_backstory = _as_str(config.get("backstory"))

        return Agent(
            role=config['role'],
            goal=final_goal,
            backstory=final_backstory,
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self._get_llm_for_agent(agent_key)
        )
    
    @agent
    def formatter_agent(self) -> Agent:
        agent_key = 'formatter_agent'
        return Agent(
            config=self.agents_config['formatter_agent'],
            verbose=True,
            allow_delegation=False,
            tools=[self.save_markdown_to_docx],
            llm=self._get_llm_for_agent(agent_key)
        )
        
    @task
    def analyze_trends_task(self) -> Task:
        cfg = self.tasks_config['analyze_trends_task'].copy()

        ctx = {
            "herbs_eng": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH_ENG", "")),
        }

        desc_raw = cfg.get("description", "")
        exp_raw  = cfg.get("expected_output", "")
        if isinstance(desc_raw, list): desc_raw = "\n".join(desc_raw)
        if isinstance(exp_raw, list):  exp_raw  = "\n".join(exp_raw)

        final_description = Template(str(desc_raw)).safe_substitute(**ctx)
        final_expected_output = Template(str(exp_raw)).safe_substitute(**ctx)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.trend_analyst_agent(),
            tools=[self.serper_tool, self.tavily_gwi, self.browse_website_tool],
            context=cfg.get('context')
        )
        
    @task
    def laboratory_data_task(self) -> Task:
        """Research evidence task"""
        cfg = self.tasks_config['laboratory_data_task'].copy()

        herbs_thai = self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH_THAI", ""))
        
        ctx = {
            "herbs_thai": herbs_thai, 
        }

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)

        tools = []
        if self.pinecone_enabled:
            tools.append(self.pinecone_search)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.herbal_laboratory_agent(),
            tools=tools,
            context=cfg.get('context')
        )
    
    @task
    def research_evidence_task(self) -> Task:
        """Research evidence task"""
        cfg = self.tasks_config['research_evidence_task'].copy()

        herb_name = self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))
        citation_format = getattr(self, "herbal_citation", "[source, p.X]")
        
        ctx = {
            "herbs": herb_name, 
            "citation_format": citation_format,
        }

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)

        tools = [
            self.pubmed_search, 
            self.pubmed_fetch, 
            self.pubmed_parse,
            self.pubmed_summary,
        ]

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.research_agent(),
            tools=tools,
            context=cfg.get('context')
        )
        
    @task
    def check_compliance_task(self) -> Task:
        """Compliance check task"""
        cfg = self.tasks_config['check_compliance_task'].copy()
        herbs_thai = self.params.get("herbs_thai", os.getenv("HERBS_FOR_RESEARCH_THAI", ""))

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        desc_raw = desc_raw.replace("{herbs_thai}", "$herbs_thai")
        out_raw  = out_raw.replace("{herbs_thai}", "$herbs_thai")

        ctx = {"herbs_thai": herbs_thai} 

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)

        return Task(
            description=final_description,          
            expected_output=final_expected_output, 
            agent=self.compliance_checker_agent(),
            tools=[self.browse_website_tool],      
        )
    
    @task
    def find_safety_data_task(self) -> Task:
        """Find safety data task"""
        cfg = self.tasks_config['find_safety_data_task'].copy()
        herbs = self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        desc_raw = desc_raw.replace("{herbs}", "$herbs")
        out_raw  = out_raw.replace("{herbs}", "$herbs")

        ctx = {"herbs": herbs} 

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)

        return Task(
            description=final_description,          
            expected_output=final_expected_output, 
            agent=self.safety_inspector_agent(),    
            tools=[self.serper_tool, self.browse_website_tool],
        )
        
    @task
    def find_clinical_toxicity_task(self) -> Task:
        """Find clinical toxicity task"""
        cfg = self.tasks_config['find_clinical_toxicity_task'].copy()
        herbs = self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", ""))

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        desc_raw = desc_raw.replace("{herbs}", "$herbs")
        out_raw  = out_raw.replace("{herbs}", "$herbs")

        ctx = {"herbs": herbs} 

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)

        return Task(
            description=final_description,          
            expected_output=final_expected_output, 
            agent=self.clinical_toxicologist_agent(),    
            tools=[self.serper_tool, self.browse_website_tool],
        )
        
    @task
    def raw_extraction_culture_task(self) -> Task:
        cfg = self.tasks_config['raw_extraction_culture_task'].copy()

        ctx = {
            "herbs_thai": self.params.get("herbs_thai", os.getenv("HERBS_FOR_RESEARCH_THAI", ""))
        }

        desc_raw = cfg.get("description", "")
        exp_raw  = cfg.get("expected_output", "")
        if isinstance(desc_raw, list): desc_raw = "\n".join(desc_raw)
        if isinstance(exp_raw, list):  exp_raw  = "\n".join(exp_raw)

        final_description = Template(str(desc_raw)).safe_substitute(**ctx)
        final_expected_output  = Template(str(exp_raw)).safe_substitute(**ctx)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.cultural_editor_agent(), 
            tools=[self.search_SAC, self.browse_website_tool],
            context=cfg.get('context')
        )
        
    @task
    def translation_and_synthesis_culture_task(self) -> Task:
        cfg = self.tasks_config['translation_and_synthesis_culture_task'].copy()

        ctx = {
            "herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", "")),
        }

        desc_raw = cfg.get("description", "")
        exp_raw  = cfg.get("expected_output", "")
        if isinstance(desc_raw, list): desc_raw = "\n".join(desc_raw)
        if isinstance(exp_raw, list):  exp_raw  = "\n".join(exp_raw)

        final_description = Template(str(desc_raw)).safe_substitute(**ctx)
        final_expected_output  = Template(str(exp_raw)).safe_substitute(**ctx)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.cultural_editor_agent(), 
            tools=[],
            context=cfg.get('context')
        )
                
    @task
    def herbal_internal_knowledge_task(self) -> Task:
        cfg = self.tasks_config['herbal_internal_knowledge_task'].copy()

        ctx = {
            "herbs_thai": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH_THAI", "")),
            "herbal_rag_context": self.herbal_context or "(No RAG context available)",
            "citation_format": getattr(self, "herbal_citation", "[source, p.X]"),
        }

        desc_raw = cfg.get("description", "")
        exp_raw  = cfg.get("expected_output", "")
        if isinstance(desc_raw, list): desc_raw = "\n".join(desc_raw)
        if isinstance(exp_raw, list):  exp_raw  = "\n".join(exp_raw)

        final_description = Template(str(desc_raw)).substitute(**ctx)
        final_expected_output = Template(str(exp_raw)).substitute(**ctx)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.internal_knowledge_agent(),
            tools=[],
            context=cfg.get('context')
        )

                
    @task
    def cultural_internal_knowledge_task(self) -> Task:
        cfg = self.tasks_config['cultural_internal_knowledge_task'].copy()

        ctx = {
            "herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", "")),
            "herbs_thai": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH_THAI", "")),
            "cultural_rag_context": self.cultural_context or "(No RAG context available)",
            "citation_format": getattr(self, "herbal_citation", "[source, p.X]"),
        }

        desc_raw = cfg.get("description", "")
        exp_raw  = cfg.get("expected_output", "")
        if isinstance(desc_raw, list): desc_raw = "\n".join(desc_raw)
        if isinstance(exp_raw, list):  exp_raw  = "\n".join(exp_raw)

        final_description = Template(str(desc_raw)).substitute(**ctx)
        final_expected_output = Template(str(exp_raw)).substitute(**ctx)

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.internal_knowledge_agent(),
            tools=[],
            context=cfg.get('context')
        )
        
    @task
    def consolidation_task(self) -> Task:
        """Final read data before writing task"""
        cfg = self.tasks_config['consolidation_task'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_description = _as_str(cfg.get("description"))
        final_expected_output = _as_str(cfg.get("expected_output"))

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.writer_agent(),
            tools=[],
            context=cfg.get('context') 
        )
        
    @task
    def planner_task(self) -> Task:
        """Planner task"""
        cfg = self.tasks_config['planner_task'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_description = _as_str(cfg.get("description"))
        final_expected_output = _as_str(cfg.get("expected_output"))

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.planner_agent(),
            tools=[],
            context=cfg.get('context') 
        )
        
    @task
    def write_article_task(self) -> Task:
        """Final article writing task"""
        cfg = self.tasks_config['write_article_task'].copy()

        ctx = {
            "herbs": self.params.get("herbs", os.getenv("HERBS_FOR_RESEARCH", "")),
            "herbs_eng": self.params.get("herbs_eng", os.getenv("HERBS_FOR_RESEARCH_ENG", "")),
            "lang": getattr(self, "lang", "en")
        }

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        desc_raw = _as_str(cfg.get("description"))
        out_raw  = _as_str(cfg.get("expected_output"))

        final_description = Template(desc_raw).safe_substitute(**ctx)
        final_expected_output = Template(out_raw).safe_substitute(**ctx)
        
        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.writer_agent(), 
            tools=[],
            context=cfg.get('context')
        )
        
    @task
    def audit_data_integrity_task(self) -> Task:
        """Planner task"""
        cfg = self.tasks_config['audit_data_integrity_task'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_description = _as_str(cfg.get("description"))
        final_expected_output = _as_str(cfg.get("expected_output"))

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.qa_auditor_agent(),
            tools=[],
            context=cfg.get('context') 
        )
    
    @task
    def audit_strategy_task(self) -> Task:
        """Planner task"""
        cfg = self.tasks_config['audit_strategy_task'].copy()

        def _as_str(v):
            if isinstance(v, list): return "\n".join(map(str, v))
            return "" if v is None else str(v)

        final_description = _as_str(cfg.get("description"))
        final_expected_output = _as_str(cfg.get("expected_output"))

        return Task(
            description=final_description,
            expected_output=final_expected_output,
            agent=self.content_strategist_agent(),
            tools=[],
            context=cfg.get('context') 
        )
    
    @task
    def convert_docx_task(self) -> Task:
        return Task(
            config=self.tasks_config['convert_docx_task'],
            agent=self.formatter_agent(),  
            tools=[self.save_markdown_to_docx],
        )
    
    @task
    def upload_docx_task(self) -> Task:
        return Task(
            config=self.tasks_config['upload_docx_task'],
            agent=self.formatter_agent(),
            tools=[self.gdrive_upload_file],
        )

    @crew
    def crew(self) -> Crew:        
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True, 
            cache=False,
        )