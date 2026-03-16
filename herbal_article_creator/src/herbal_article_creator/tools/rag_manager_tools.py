import os
from .common_rag import create_rag_tool, RAGEngine
from typing import Dict, Tuple
from src.herbal_article_creator.tools.gdrive_browse_for_rag import (
    gdrive_fetch_pdfs_for_rag,
    gdrive_list_pdfs_in_folder_for_rag
)
from src.herbal_article_creator.tools.pinecone_tools import build_herb_query

class RAGManager:
    """Manage RAG engines for Crew"""
    
    def __init__(self):
        self.engines = {}
        self.contexts = {}
        self.citation_formats = {}
    
    def fetch_pdf_paths_from_folder(self, folder_id: str, query: str | None = None, max_files: int = 10):
        """
        Find and download all PDF files from your Google Drive folder.
        Restore them to a list of local file paths.

        Args:
            folder_id (str): Google Drive Folder ID
            query (str): File name search (optional)
            max_files (int): Maximum number of files to load

        Returns:
            list[str]: List of paths of downloaded PDF files
        """
        print(f"🔍 Using Tool: gdrive_list_pdfs_in_folder_for_rag")
        files = gdrive_list_pdfs_in_folder_for_rag.run(folder_id=folder_id, query=query, max_files=max_files)
        print(f"📄 Found {len(files)} file(s)")

        if not files:
            print("The file was not found in this folder or the Service Account does not have permission to access it.")
            return []

        for f in files:
            print(f"- {f['name']} ({f['id']})")

        picked = gdrive_fetch_pdfs_for_rag.run([f["id"] for f in files])
        paths = picked.get("paths", [])
        print(f"✅ Downloaded {len(paths)} file(s):")
        for p in paths:
            print(f"  - {p}")

        return paths
        
    def setup_herbal_processing(self) -> Tuple[str, str]:
        """
        Setup RAG for Herbal Processing JSON
        
        Returns:
            (context, citation_format)
        """
        if 'herbal_processing' not in self.engines:
            print("[RAG] Loading Herbal_processing.json...")
            
            # Use optimized queries with herb names
            rag, context = create_rag_tool(
                sources="data/json/Herbal_processing.json",
                source_type="json",
                target_label="herbal_processing",
                seed_queries=[
                    build_herb_query(aspect="การแปรรูป วิธีการสกัด extraction"),
                    build_herb_query(aspect="การทำผงแห้ง การอบแห้ง drying"),
                    build_herb_query(aspect="การสกัด การต้ม การคั้น oil extraction"),
                    build_herb_query(aspect="สูตรผลิตภัณฑ์ สบู่ ครีม formulation"),
                    build_herb_query(aspect="มาตรฐานคุณภาพ การควบคุม quality control"),
                    build_herb_query(aspect="ความปลอดภัย พารามิเตอร์ safety"),
                ],
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.5
            )
            
            self.engines['herbal_processing'] = rag
            self.contexts['herbal_processing'] = context
            self.citation_formats['herbal_processing'] = rag.get_citation_format()
            
            print(f"[RAG] ✓ Loaded {len(context)} chars")
            print(f"[RAG]   Citation: {rag.get_citation_format()}")
        
        return (
            self.contexts['herbal_processing'],
            self.citation_formats['herbal_processing']
        )
    
    def setup_thai_medicine(self) -> Tuple[str, str]:
        """
        Setup RAG for Thai Traditional Medicine JSON
        
        Returns:
            (context, citation_format)
        """
        if 'thai_medicine' not in self.engines:
            print("[RAG] Loading Herbs_traditional_Thai_medicine_in_the_lives_of_Thai_people.json...")
            
            # Use optimized queries
            rag, context = create_rag_tool(
                sources="data/json/Herbs_traditional_Thai_medicine_in_the_lives_of_Thai_people.json",
                source_type="json",
                target_label="thai_medicine",
                seed_queries=[
                    build_herb_query(aspect="ในแพทย์แผนไทย การใช้แบบดั้งเดิม traditional medicine"),
                    build_herb_query(aspect="ภูมิปัญญาไทย วิถีชีวิต wisdom culture"),
                    build_herb_query(aspect="รสยา ทฤษฎีธาตุ element theory"),
                    build_herb_query(aspect="ตำรับโบราณ สูตรยา ancient formula"),
                    "ประวัติศาสตร์แพทย์แผนไทย ยุคสมัย",  # Generic - no herb name needed
                    "กฎหมาย นโยบาย พ.ร.บ. บัญชียาหลัก",  # Generic
                ],
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.4
            )
            
            self.engines['thai_medicine'] = rag
            self.contexts['thai_medicine'] = context
            self.citation_formats['thai_medicine'] = rag.get_citation_format()
            
            print(f"[RAG] ✓ Loaded {len(context)} chars")
            print(f"[RAG]   Citation: {rag.get_citation_format()}")
        
        return (
            self.contexts['thai_medicine'],
            self.citation_formats['thai_medicine']
        )
        
    def setup_nutrition_wisdom(self) -> Tuple[str, str]:
        """
        Setup RAG for Nutrition in Thai Wisdom JSON
        
        Returns:
            (context, citation_format)
        """
        if 'nutrition_wisdom' not in self.engines:
            print("[RAG] Loading Nutrition_in_Thai_wisdom.json...")
            
            # Use optimized queries
            rag, context = create_rag_tool(
                sources="data/json/Nutrition_in_Thai_wisdom.json",
                source_type="json",
                target_label="nutrition_wisdom",
                seed_queries=[
                    build_herb_query(aspect="โภชนาการ คุณค่าทางโภชนาการ nutrition"),
                    build_herb_query(aspect="อาหารเป็นยา food as medicine"),
                    build_herb_query(aspect="ในอาหารไทย การประกอบอาหาร cooking"),
                    build_herb_query(aspect="ประโยชน์ต่อสุขภาพ health benefits"),
                    "หลักโภชนาการไทย สมดุล",  # Generic
                    "ภูมิปัญญาการถนอมอาหาร",  # Generic
                ],
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.5
            )
            
            self.engines['nutrition_wisdom'] = rag
            self.contexts['nutrition_wisdom'] = context
            self.citation_formats['nutrition_wisdom'] = rag.get_citation_format()
            
            print(f"[RAG] ✓ Loaded {len(context)} chars")
            print(f"[RAG]   Citation: {rag.get_citation_format()}")
        
        return (
            self.contexts['nutrition_wisdom'],
            self.citation_formats['nutrition_wisdom']
        )
    
    def setup_healthy_menus(self) -> Tuple[str, str]:
        """Setup RAG for Healthy Menus document"""
        if 'healthy_menus' not in self.engines:
            # Use optimized queries
            rag, context = create_rag_tool(
                sources="/Users/topgun/Desktop/doc/190_healthy_menus.pdf",
                source_type="pdf",
                target_label="healthy_menus",
                seed_queries=[
                    build_herb_query(aspect="ในเมนูอาหาร สูตรอาหาร menu recipe"),
                    build_herb_query(aspect="กินเพื่อสุขภาพ healthy eating"),
                    "หลักการกินเพื่อสุขภาพ",
                    "ใยอาหาร วิธีปรุง",
                ]
            )
            
            self.engines['healthy_menus'] = rag
            self.contexts['healthy_menus'] = context
            self.citation_formats['healthy_menus'] = rag.get_citation_format()
            
            print(f"[RAG] Healthy Menus loaded: {len(context)} chars")
        
        return (
            self.contexts['healthy_menus'],
            self.citation_formats['healthy_menus']
        )
    
    def setup_herbal_pdf_documents(self) -> Tuple[str, str]:
        """
        Setup RAG for herbal-related documents from Google Drive
        
        Returns:
            (context, citation_format)
        """
        if 'herbal_docs' not in self.engines:
            print("[RAG] Loading herbal documents...")
            
            folder_id = os.getenv("GOOGLE_FOLDER_ID")
            paths = self.fetch_pdf_paths_from_folder(folder_id, query=None, max_files=5)
            print("\nPDF paths returned:", paths)
            
            # Use optimized queries with herb names
            rag, context = create_rag_tool(
                sources=paths,
                source_type="pdf",
                target_label="herbal_docs",
                seed_queries=[
                    build_herb_query(aspect="สรรพคุณ properties medicinal uses"),
                    build_herb_query(aspect="การใช้ประโยชน์ applications usage"),
                    build_herb_query(aspect="สารสำคัญ active compounds chemical"),
                    build_herb_query(aspect="การปลูก cultivation growing"),
                    build_herb_query(aspect="การเตรียม preparation processing"),
                    build_herb_query(aspect="ข้อบ่งใช้ indications diseases"),
                ],
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.6
            )
            
            self.engines['herbal_docs'] = rag
            self.contexts['herbal_docs'] = context
            self.citation_formats['herbal_docs'] = rag.get_citation_format()
            
            print(f"[RAG] Loaded {len(context)} chars from herbal documents")
            print(f"[RAG] Citation format: {rag.get_citation_format()}")
        
        return (
            self.contexts['herbal_docs'],
            self.citation_formats['herbal_docs']
        )
    
    def setup_cultural_pdf_documents(self) -> Tuple[str, str]:
        """Setup RAG for cultural/nutrition documents"""
        if 'cultural_docs' not in self.engines:
            print("[RAG] Loading cultural documents...")
            
            # Generic queries - not herb-specific
            rag, context = create_rag_tool(
                sources=[
                    "data/pdf/190_healthy_menus.pdf",
                ],
                source_type="pdf",
                target_label="cultural_docs",
                seed_queries=[
                    "ภูมิปัญญาไทยด้านสมุนไพร การใช้แบบดั้งเดิม",
                    "วิถีการใช้สมุนไพรของไทย ประเพณี",
                    "โภชนาการในภูมิปัญญาไทย อาหารเพื่อสุขภาพ",
                    "การแปรรูปสมุนไพรแบบไทย วิธีดั้งเดิม",
                ],
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True
            )
            
            self.engines['cultural_docs'] = rag
            self.contexts['cultural_docs'] = context
            self.citation_formats['cultural_docs'] = rag.get_citation_format()
            
            print(f"[RAG] Loaded {len(context)} chars from cultural documents")
        
        return (
            self.contexts['cultural_docs'],
            self.citation_formats['cultural_docs']
        )
    
    def setup_herbal_documents_combined(self) -> Tuple[str, str]:
        """
        Setup RAG for multiple herbal documents (for trend_analyst_agent)
        Combine Herbal Processing + Thai Medicine + PDFs
        
        Returns:
            (combined_context, citation_format)
        """
        if 'herbal_combined' not in self.engines:
            print("[RAG] Loading combined herbal documents (JSON + PDF)...")
            
            # ===== 1. Load JSON files =====
            print("  [1/2] Loading JSON files...")
            rag_json = RAGEngine(
                sources=[
                    "data/json/Herbal_processing.json",
                    "data/json/Herbs_traditional_Thai_medicine_in_the_lives_of_Thai_people.json",
                ],
                source_type="json",
                target_label="herbal_json",
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.6
            )
            
            folder_id = os.getenv("GOOGLE_FOLDER_ID")
            paths = self.fetch_pdf_paths_from_folder(folder_id, query=None, max_files=5)
            print("\nPDF paths returned:", paths)
            
            # ===== 2. Load PDF files =====
            print("  [2/2] Loading PDF files...")
            rag_pdf = RAGEngine(
                sources=paths,
                source_type="pdf",
                target_label="herbal_pdf",
                chunk_size=1000,
                chunk_overlap=120,
                use_mmr=True,
                mmr_lambda=0.6
            )
            
            print(f"  ✓ JSON: {len(rag_json.chunks)} chunks")
            print(f"  ✓ PDF:  {len(rag_pdf.chunks)} chunks")
            
            # ===== 3. Create context from 2 sources =====
            # Use optimized queries
            seed_queries = [
                build_herb_query(aspect="สรรพคุณ properties medicinal"),
                build_herb_query(aspect="การใช้ประโยชน์ applications"),
                build_herb_query(aspect="การปลูก cultivation"),
                build_herb_query(aspect="การแปรรูป processing extraction"),
                build_herb_query(aspect="ภูมิปัญญาไทย traditional wisdom"),
            ]
            
            # Retrieve context from JSON
            context_json = rag_json.build_context(seed_queries, k=3, max_chars=5000)
            
            # Retrieve context from PDF
            context_pdf = rag_pdf.build_context(seed_queries, k=3, max_chars=5000)
            
            # Combine context
            combined_context = f"""
                === จากไฟล์ JSON ===
                {context_json}

                === จากไฟล์ PDF ===
                {context_pdf}
                """.strip()
            
            # Keep both engines
            self.engines['herbal_json'] = rag_json
            self.engines['herbal_pdf'] = rag_pdf
            self.engines['herbal_combined'] = {
                'json': rag_json,
                'pdf': rag_pdf
            }
            
            self.contexts['herbal_combined'] = combined_context
            
            # Citation format
            self.citation_formats['herbal_combined'] = (
                f"JSON: {rag_json.get_citation_format()} | "
                f"PDF: {rag_pdf.get_citation_format()}"
            )
            
            print(f"[RAG] ✓ Combined context: {len(combined_context):,} chars")
            print(f"[RAG]   Citations: {self.citation_formats['herbal_combined']}")
        
        return (
            self.contexts['herbal_combined'],
            self.citation_formats['herbal_combined']
        )
    
    def setup_cultural_documents_json_combined(self) -> Tuple[str, str]:
        """
        Setup RAG for cultural documents (for cultural_editor_agent)
        Focus on Thai Medicine + Nutrition Wisdom
        
        Returns:
            (context, citation_format)
        """
        if 'cultural_combined' not in self.engines:
            print("[RAG] Loading cultural documents (JSON)...")
            
            rag = RAGEngine(
                sources=[
                    "data/json/Nutrition_in_Thai_wisdom.json",
                ],
                source_type="json",
                target_label="cultural_combined",
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.5
            )
            
            # Use optimized queries with both Thai and scientific names
            context = rag.build_context(
                queries=[
                    build_herb_query(aspect="ภูมิปัญญาไทย การใช้แบบดั้งเดิม traditional Thai wisdom"),
                    build_herb_query(aspect="รสยา สรรพคุณ Thai medicine theory"),
                    build_herb_query(aspect="ธาตุเจ้าเรือน ปรับสมดุล element balance"),
                    build_herb_query(aspect="อาหารเป็นยา food as medicine"),
                    build_herb_query(aspect="ตำรับอาหาร โรค NCDs recipe disease"),
                    build_herb_query(aspect="สร้างภูมิคุ้มกัน immunity"),
                    build_herb_query(aspect="Thai traditional medicine properties"),
                ],
                k=10,
                max_chars=8000
            )
            
            self.engines['cultural_combined'] = rag
            self.contexts['cultural_combined'] = context
            self.citation_formats['cultural_combined'] = rag.get_citation_format()
            
            print(f"[RAG] ✓ Loaded {len(context)} chars from cultural sources")
        
        return (
            self.contexts['cultural_combined'],
            self.citation_formats['cultural_combined']
        )

    def setup_cultural_documents_combined(self) -> Tuple[str, str]:
        """
        Setup RAG for cultural documents (for cultural_editor_agent)
        Combine Thai Medicine + Nutrition Wisdom + PDF
        
        Returns:
            (combined_context, citation_format)
        """
        if 'cultural_docs_combined' not in self.engines:
            print("[RAG] Loading combined cultural documents (JSON + PDF)...")
            
            # ===== 1. Load JSON files =====
            print("  [1/2] Loading JSON files...")
            rag_json = RAGEngine(
                sources=[
                    "data/json/Herbs_traditional_Thai_medicine_in_the_lives_of_Thai_people.json",
                    "data/json/Nutrition_in_Thai_wisdom.json",
                ],
                source_type="json",
                target_label="cultural_json",
                chunk_size=1200,
                chunk_overlap=150,
                use_mmr=True,
                mmr_lambda=0.6
            )
            
            # ===== 2. Load PDF files =====
            print("  [2/2] Loading PDF files...")
            rag_pdf = RAGEngine(
                sources=[
                    "data/pdf/190_healthy_menus.pdf",
                ],
                source_type="pdf",
                target_label="cultural_pdf",
                chunk_size=1000,
                chunk_overlap=120,
                use_mmr=True,
                mmr_lambda=0.6
            )
            
            print(f"  ✓ JSON: {len(rag_json.chunks)} chunks")
            print(f"  ✓ PDF:  {len(rag_pdf.chunks)} chunks")
            
            # ===== 3. Create context from 2 sources =====
            # Use optimized queries
            seed_queries = [
                build_herb_query(aspect="ภูมิปัญญาไทย วิถีดั้งเดิม traditional wisdom"),
                build_herb_query(aspect="วัฒนธรรมการใช้ ประเพณี culture tradition"),
                build_herb_query(aspect="โภชนาการ อาหารเพื่อสุขภาพ nutrition health"),
                build_herb_query(aspect="การแปรรูปแบบไทย วิธีโบราณ traditional processing"),
                "ประวัติศาสตร์แพทย์แผนไทย",  # Generic
            ]
            
            # Retrieve context from JSON
            context_json = rag_json.build_context(seed_queries, k=3, max_chars=5000)
            
            # Retrieve context from PDF
            context_pdf = rag_pdf.build_context(seed_queries, k=3, max_chars=5000)
            
            # Combine context
            combined_context = f"""
                === จากไฟล์ JSON ===
                {context_json}

                === จากไฟล์ PDF ===
                {context_pdf}
                """.strip()
            
            # Keep both engines
            self.engines['cultural_json'] = rag_json
            self.engines['cultural_pdf'] = rag_pdf
            self.engines['cultural_docs_combined'] = {
                'json': rag_json,
                'pdf': rag_pdf
            }
            
            self.contexts['cultural_docs_combined'] = combined_context
            
            # Citation format
            self.citation_formats['cultural_docs_combined'] = (
                f"JSON: {rag_json.get_citation_format()} | "
                f"PDF: {rag_pdf.get_citation_format()}"
            )
            
            print(f"[RAG] ✓ Combined context: {len(combined_context):,} chars")
            print(f"[RAG]   Citations: {self.citation_formats['cultural_docs_combined']}")
        
        return (
            self.contexts['cultural_docs_combined'],
            self.citation_formats['cultural_docs_combined']
        )
    
    def get_all_contexts(self) -> Dict[str, str]:
        """Get all loaded contexts"""
        return {
            'herbal_context': self.contexts.get('herbal_docs', ''),
            'cultural_context': self.contexts.get('cultural_docs', ''),
            'herbal_citation': self.citation_formats.get('herbal_docs', '[doc, p.X]'),
            'cultural_citation': self.citation_formats.get('cultural_docs', '[doc, p.X]')
        }
    
    def get_engine(self, name: str):
        """Get RAG engine by name"""
        return self.engines.get(name)

rag_manager = RAGManager()