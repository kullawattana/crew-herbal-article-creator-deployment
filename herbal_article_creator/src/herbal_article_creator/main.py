"""
Main entry point for Herbal Article Creator
Run the crew to generate Thai herbal wellness articles
"""
import os
from dotenv import load_dotenv
import litellm

load_dotenv()

open_log = os.getenv("LANGFUSE_LOG_OPEN", "true").lower()
if open_log == "false":
    print("⚠️ Langfuse logging disabled.")
else:
    print("✅ Langfuse logging enabled.")
    os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("LANGFUSE_PUBLIC_KEY")
    os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("LANGFUSE_SECRET_KEY")
    os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

import sys, os, warnings
from pathlib import Path
from datetime import datetime
from herbal_article_creator.crew import HerbalArticleCreator

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def setup_environment():
    """Setup environment variables"""
    try:
        load_dotenv()
    except ImportError:
        print("python-dotenv not installed. Using system environment variables.")
        
    print(f"LLM_MODEL_NAME: {os.getenv('LLM_MODEL_NAME')}")
    required_vars = ["TAVILY_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

def write_task_log(i, timestamp, task_output, output_dir: Path):
    output_file = output_dir / f"task_{i+1}_{timestamp}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(task_output.raw))
    print(f"✅ Task {i+1} saved: {output_file}")   
    
def write_single_log(result_str, timestamp, output_dir: Path):
    full_output_path = output_dir / f"full_output_{timestamp}.txt"
    with open(full_output_path, "w", encoding="utf-8") as f:
        f.write(result_str)
    print(f"✅ Full output saved: {full_output_path}")
    
def write_exception_log(result_str, timestamp, output_dir: Path):
    output_path = output_dir / f"output_{timestamp}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result_str)
    print(f"✅ Output saved: {output_path}")

def save_crew_result(result, result_str, output_dir: Path):
    """
    CrewAI's combined output recording functionality (with both tasks_output and fallback)
    Parameters
    ----------
    result : object
        The result of running crew.run() or run_crew().
    result_str : str
        Full result text (string)
    output_dir : Path
        Path of the folder to use to save the file
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # tasks_output checked
        if hasattr(result, "tasks_output") and result.tasks_output:
            tasks = result.tasks_output

            #Task
            for i, task_output in enumerate(tasks):                
                write_task_log(i, timestamp, task_output, output_dir)
            
        else:
            #Not have tasks_output -> save in single file
            write_single_log(result_str, timestamp, output_dir)

    except Exception as e:
        print(f"Using fallback save method: {e}")
        write_exception_log(result_str, timestamp, output_dir)

def run():
    """Run the Herbal Article Creator crew with performance metrics"""
    import psutil
    import time
    from langchain.callbacks import get_openai_callback

    print("="*80)
    print("🌿 Herbal Article Creator - Starting...")
    print("="*80)

    setup_environment()

    herbs = os.getenv("HERBS_FOR_RESEARCH", "")
    herbs_thai = os.getenv("HERBS_FOR_RESEARCH_THAI", "")
    herbs_eng = os.getenv("HERBS_FOR_RESEARCH_ENG", "")
    current_lang = os.getenv("OUTPUT_LANG", "en")
    llm_mode = os.getenv('LLM_MODE', 'model')
    max_calls = os.getenv('RESEARCH_MAX_CALLS', '6')

    print(f"OUTPUT_LANG = {current_lang}")
    print(f"\n📋 Research Target Scientific Name: {herbs}")
    print(f"📋 Research Target Thai: {herbs_thai}")
    print(f"📋 Research Target English: {herbs_eng}")
    print(f"Max Research Calls: {max_calls}")
    print("\n" + "="*80)

    try:
        crew_instance = HerbalArticleCreator(params={"herbs": herbs})
    except Exception as e:
        print(f"Error creating crew: {e}")
        sys.exit(1)

    inputs = {
        "herbs": herbs, 
        "herbs_eng": herbs_eng, 
        "herbs_thai": herbs_thai, 
        "lang": current_lang
    }

    # === Benchmark Setup ===
    print("\n Running crew with performance tracking...\n")
    process = psutil.Process()
    cpu_before = psutil.cpu_percent()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    start_time = time.time()

    try:
        with get_openai_callback() as cb:
            result = crew_instance.crew().kickoff(inputs=inputs)

            # === Metrics Collection ===
            end_time = time.time()
            cpu_after = psutil.cpu_percent()
            mem_after = process.memory_info().rss / 1024 / 1024

            print("\n=== CrewAI Evaluation Results ===")
            print(f"Runtime: {end_time - start_time:.2f} seconds")
            print(f"CPU usage: {cpu_after - cpu_before:.2f}%")
            print(f"Memory usage change: {mem_after - mem_before:.2f} MB")
            print(f"Tokens used: {cb.total_tokens}")
            print(f"Total cost: ${cb.total_cost:.5f}")

            # Optional: Save benchmark to file
            output_dir = Path("outputs")
            output_dir.mkdir(exist_ok=True)
            with open(output_dir / f"benchmark_{llm_mode.replace('/', '_')}.json", "w") as f:
                import json
                json.dump({
                    "model": llm_mode,
                    "herbs": herbs,
                    "runtime_sec": round(end_time - start_time, 2),
                    "cpu_percent": round(cpu_after - cpu_before, 2),
                    "memory_mb_change": round(mem_after - mem_before, 2),
                    "total_tokens": cb.total_tokens,
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_cost": round(cb.total_cost, 5)
                }, f, indent=2)

    except Exception as e:
        print(f"\n Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # === Save results ===
    print("\n" + "="*80)
    print("💾 Saving results...")
    print("="*80)

    result_str = str(result)
    save_crew_result(result, result_str, Path("outputs"))

    print("\n" + "="*80)
    print("✨ Process completed successfully!")
    print("="*80)

def train():
    """
    Train the crew for a given number of iterations.
    """
    herbs = os.getenv("HERBS_FOR_RESEARCH")
    herbs_thai = os.getenv("HERBS_FOR_RESEARCH_THAI")
    inputs = {
        'herbs': herbs,
        'herbs_thai': herbs_thai
    }

    try:
        HerbalArticleCreator().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        HerbalArticleCreator().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    herbs = os.getenv("HERBS_FOR_RESEARCH")
    herbs_thai = os.getenv("HERBS_FOR_RESEARCH_THAI")
    inputs = {
        'herbs': herbs,
        'herbs_thai': herbs_thai
    }
    try:
        HerbalArticleCreator().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def benchmark():
    """
    Run benchmark comparison: No-RAG LLM vs Single-Agent RAG vs Multi-Agent.

    Controlled by environment variables:
        HERBS_FOR_RESEARCH        Scientific name  (required)
        HERBS_FOR_RESEARCH_ENG    English name     (required)
        HERBS_FOR_RESEARCH_THAI   Thai name        (required)
        OUTPUT_LANG               en | th          (default: en)
        BENCHMARK_NO_RAG          true | false     (default: true)
        BENCHMARK_SINGLE_RAG      true | false     (default: true)
        BENCHMARK_MULTI_AGENT     true | false     (default: true)
        BENCHMARK_MULTI_PRECOMP   path to existing multi-agent output .txt
        BENCHMARK_REFERENCE_FILE  path to gold-standard reference .txt
        BENCHMARK_BUILD_MFS       true | false     (default: true)
        BENCHMARK_MFS_FILE        path to pre-built MFS JSON (skips build)
        BENCHMARK_PUBMED_TOP_K    int              (default: 3)
        BENCHMARK_PINECONE_TOP_K  int              (default: 5)
        BENCHMARK_INTER_RATER     true | false     (default: true)
        BENCHMARK_BLIND           true | false     (default: true)
    """
    from herbal_article_creator.benchmark.runner import BenchmarkRunner
    from herbal_article_creator.benchmark.report import print_report, save_markdown

    setup_environment()

    herbs = os.getenv("HERBS_FOR_RESEARCH", "")
    herbs_eng = os.getenv("HERBS_FOR_RESEARCH_ENG", "")
    herbs_thai = os.getenv("HERBS_FOR_RESEARCH_THAI", "")
    lang = os.getenv("OUTPUT_LANG", "en")

    if not herbs or not herbs_eng or not herbs_thai:
        print("Error: HERBS_FOR_RESEARCH, HERBS_FOR_RESEARCH_ENG, "
              "and HERBS_FOR_RESEARCH_THAI must all be set.")
        sys.exit(1)

    def _flag(key: str, default: bool = True) -> bool:
        return os.getenv(key, str(default)).lower() not in ("false", "0", "no")

    runner = BenchmarkRunner(
        herbs=herbs,
        herbs_eng=herbs_eng,
        herbs_thai=herbs_thai,
        lang=lang,
        run_no_rag=_flag("BENCHMARK_NO_RAG"),
        run_single_rag=_flag("BENCHMARK_SINGLE_RAG"),
        run_multi_agent=_flag("BENCHMARK_MULTI_AGENT"),
        multi_agent_precomputed_file=os.getenv("BENCHMARK_MULTI_PRECOMP"),
        reference_file=os.getenv("BENCHMARK_REFERENCE_FILE"),
        build_mfs=_flag("BENCHMARK_BUILD_MFS"),
        mfs_file=os.getenv("BENCHMARK_MFS_FILE"),
        pubmed_top_k=int(os.getenv("BENCHMARK_PUBMED_TOP_K", "3")),
        pinecone_top_k=int(os.getenv("BENCHMARK_PINECONE_TOP_K", "5")),
        run_inter_rater=_flag("BENCHMARK_INTER_RATER"),
        blind_evaluation=_flag("BENCHMARK_BLIND"),
        output_dir="outputs",
    )

    results = runner.run()
    print_report(results)
    save_markdown(results, output_dir="outputs")


def ablation():
    """
    Run ablation study: systematically disable components to measure contribution.

    Controlled by environment variables:
        HERBS_FOR_RESEARCH        Scientific name  (required)
        HERBS_FOR_RESEARCH_ENG    English name     (required)
        HERBS_FOR_RESEARCH_THAI   Thai name        (required)
        OUTPUT_LANG               en | th          (default: en)
        ABLATION_CONFIGS          comma-separated config names
                                  (default: all — baseline,+pubmed,+pinecone,+pubmed+pinecone,+multi_agent)
    """
    from herbal_article_creator.benchmark.ablation.runner import AblationRunner

    setup_environment()

    herbs = os.getenv("HERBS_FOR_RESEARCH", "")
    herbs_eng = os.getenv("HERBS_FOR_RESEARCH_ENG", "")
    herbs_thai = os.getenv("HERBS_FOR_RESEARCH_THAI", "")
    lang = os.getenv("OUTPUT_LANG", "en")

    if not herbs or not herbs_eng or not herbs_thai:
        print("Error: HERBS_FOR_RESEARCH, HERBS_FOR_RESEARCH_ENG, "
              "and HERBS_FOR_RESEARCH_THAI must all be set.")
        sys.exit(1)

    configs_env = os.getenv("ABLATION_CONFIGS", "")
    configs = [c.strip() for c in configs_env.split(",") if c.strip()] or None

    runner = AblationRunner(
        herbs=herbs,
        herbs_eng=herbs_eng,
        herbs_thai=herbs_thai,
        lang=lang,
        configs=configs,
        output_dir="outputs",
    )

    results = runner.run()
    runner.print_table(results)
    runner.print_deltas(results)
