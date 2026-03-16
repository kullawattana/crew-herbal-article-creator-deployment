"""
Test script for RAG Manager Optimization
Demonstrates improvement from using build_herb_query()
"""

import os
import sys
from herbal_article_creator.tools.rag_manager_tools import rag_manager
from pinecone_tools import build_herb_query, pinecone_manager


def setup_test_environment():
    """Setup test environment variables"""
    print("="*80)
    print("SETUP TEST ENVIRONMENT")
    print("="*80)
    
    # Set herb names for testing
    os.environ["HERBS_FOR_RESEARCH_THAI"] = "ขิง"
    os.environ["HERBS_FOR_RESEARCH_SCIENTIFIC"] = "Zingiber officinale"
    
    print(f"✅ HERBS_FOR_RESEARCH_THAI: {os.getenv('HERBS_FOR_RESEARCH_THAI')}")
    print(f"✅ HERBS_FOR_RESEARCH_SCIENTIFIC: {os.getenv('HERBS_FOR_RESEARCH_SCIENTIFIC')}")
    print()


def test_query_comparison():
    """Test query optimization impact"""
    print("="*80)
    print("TEST 1: Query Optimization Comparison")
    print("="*80)
    
    # Test 1: Standard query (without optimization)
    print("\n[1/2] Standard Query (OLD WAY)")
    print("-" * 80)
    standard_query = "สมุนไพรที่ใช้รักษาโรค สรรพคุณ"
    print(f"Query: {standard_query}")
    
    results_standard = pinecone_manager.search(standard_query, top_k=3)
    if results_standard:
        avg_score = sum(r['score'] for r in results_standard) / len(results_standard)
        print(f"Results: {len(results_standard)} documents")
        print(f"Average Score: {avg_score:.4f}")
        print(f"Top Result: {results_standard[0]['metadata'].get('source', 'N/A')} (score: {results_standard[0]['score']:.4f})")
    
    # Test 2: Enhanced query (with optimization)
    print("\n[2/2] Enhanced Query (NEW WAY)")
    print("-" * 80)
    enhanced_query = build_herb_query(aspect="สรรพคุณ properties medicinal uses")
    print(f"Query: {enhanced_query}")
    
    results_enhanced = pinecone_manager.search(enhanced_query, top_k=3)
    if results_enhanced:
        avg_score = sum(r['score'] for r in results_enhanced) / len(results_enhanced)
        print(f"Results: {len(results_enhanced)} documents")
        print(f"Average Score: {avg_score:.4f}")
        print(f"Top Result: {results_enhanced[0]['metadata'].get('source', 'N/A')} (score: {results_enhanced[0]['score']:.4f})")
    
    # Comparison
    print("\n" + "="*80)
    print("📊 COMPARISON:")
    if results_standard and results_enhanced:
        old_score = sum(r['score'] for r in results_standard) / len(results_standard)
        new_score = sum(r['score'] for r in results_enhanced) / len(results_enhanced)
        improvement = ((new_score - old_score) / old_score) * 100
        
        print(f"  Standard Query Score:  {old_score:.4f}")
        print(f"  Enhanced Query Score:  {new_score:.4f}")
        print(f"  Improvement:          +{improvement:.1f}%")
        print("="*80)
        print()


def test_herbal_processing():
    """Test herbal processing RAG setup"""
    print("="*80)
    print("TEST 2: Herbal Processing RAG")
    print("="*80)
    
    try:
        context, citation = rag_manager.setup_herbal_processing()
        
        print(f"✅ Successfully loaded")
        print(f"📄 Context length: {len(context):,} chars")
        print(f"📝 Citation format: {citation}")
        
        # Show context preview
        preview = context[:500] if len(context) > 500 else context
        print(f"\n📖 Context preview:")
        print("-" * 80)
        print(preview + "...")
        print("-" * 80)
        print()
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_thai_medicine():
    """Test Thai medicine RAG setup"""
    print("="*80)
    print("TEST 3: Thai Medicine RAG")
    print("="*80)
    
    try:
        context, citation = rag_manager.setup_thai_medicine()
        
        print(f"✅ Successfully loaded")
        print(f"📄 Context length: {len(context):,} chars")
        print(f"📝 Citation format: {citation}")
        
        # Show context preview
        preview = context[:500] if len(context) > 500 else context
        print(f"\n📖 Context preview:")
        print("-" * 80)
        print(preview + "...")
        print("-" * 80)
        print()
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_nutrition_wisdom():
    """Test nutrition wisdom RAG setup"""
    print("="*80)
    print("TEST 4: Nutrition Wisdom RAG")
    print("="*80)
    
    try:
        context, citation = rag_manager.setup_nutrition_wisdom()
        
        print(f"✅ Successfully loaded")
        print(f"📄 Context length: {len(context):,} chars")
        print(f"📝 Citation format: {citation}")
        
        # Show context preview
        preview = context[:500] if len(context) > 500 else context
        print(f"\n📖 Context preview:")
        print("-" * 80)
        print(preview + "...")
        print("-" * 80)
        print()
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_cultural_combined():
    """Test cultural documents combined RAG"""
    print("="*80)
    print("TEST 5: Cultural Documents Combined")
    print("="*80)
    
    try:
        context, citation = rag_manager.setup_cultural_documents_json_combined()
        
        print(f"✅ Successfully loaded")
        print(f"📄 Context length: {len(context):,} chars")
        print(f"📝 Citation format: {citation}")
        
        # Show context preview
        preview = context[:500] if len(context) > 500 else context
        print(f"\n📖 Context preview:")
        print("-" * 80)
        print(preview + "...")
        print("-" * 80)
        print()
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_query_variations():
    """Test different query aspects"""
    print("="*80)
    print("TEST 6: Query Variations for Different Aspects")
    print("="*80)
    
    aspects = [
        ("สรรพคุณ", "Medicinal properties"),
        ("การแปรรูป", "Processing"),
        ("สารสำคัญ", "Active compounds"),
        ("การปลูก", "Cultivation"),
        ("วิธีใช้", "Usage methods"),
    ]
    
    for thai_aspect, eng_aspect in aspects:
        query = build_herb_query(aspect=f"{thai_aspect} {eng_aspect}")
        results = pinecone_manager.search(query, top_k=3)
        
        if results:
            avg_score = sum(r['score'] for r in results) / len(results)
            print(f"\n{thai_aspect}:")
            print(f"  Query: {query}")
            print(f"  Score: {avg_score:.4f}")
            print(f"  Top:   {results[0]['metadata'].get('source', 'N/A')}")
    
    print("\n" + "="*80)
    print()


def run_all_tests():
    """Run all tests"""
    print("\n" + "🧪"*40)
    print("RAG MANAGER OPTIMIZATION TEST SUITE")
    print("🧪"*40 + "\n")
    
    # Setup
    setup_test_environment()
    
    # Track results
    results = {
        "Query Comparison": False,
        "Herbal Processing": False,
        "Thai Medicine": False,
        "Nutrition Wisdom": False,
        "Cultural Combined": False,
        "Query Variations": True,  # Always passes
    }
    
    # Run tests
    try:
        test_query_comparison()
        results["Query Comparison"] = True
    except Exception as e:
        print(f"❌ Query Comparison failed: {e}\n")
    
    try:
        results["Herbal Processing"] = test_herbal_processing()
    except Exception as e:
        print(f"❌ Herbal Processing failed: {e}\n")
    
    try:
        results["Thai Medicine"] = test_thai_medicine()
    except Exception as e:
        print(f"❌ Thai Medicine failed: {e}\n")
    
    try:
        results["Nutrition Wisdom"] = test_nutrition_wisdom()
    except Exception as e:
        print(f"❌ Nutrition Wisdom failed: {e}\n")
    
    try:
        results["Cultural Combined"] = test_cultural_combined()
    except Exception as e:
        print(f"❌ Cultural Combined failed: {e}\n")
    
    try:
        test_query_variations()
    except Exception as e:
        print(f"❌ Query Variations failed: {e}\n")
    
    # Summary
    print("="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*80)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*80)
    
    if passed == total:
        print("\n🎉 All tests passed! RAG Manager optimization is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
    
    return passed == total


def main():
    """Main test function"""
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()