#!/usr/bin/env python3
"""
Unit test for docx_tools.py - tests markdown to docx conversion
"""
import os
from docx_tools import SaveMarkdownToDocxTool

SAMPLE_MARKDOWN = """# Turmeric: From Ancient Wisdom to Modern Strategy
## Herbal in Wellness Trends
The COVID-19 pandemic has accelerated various wellness trends, including the use of superfoods that claim to boost immunity. Turmeric, ginger, and other spices have seen a significant increase in popularity as consumers search for food ingredients that will enhance their immune system. In the 14 weeks to June 6, US retail sales of ginger rose 94%, turmeric 68%, and garlic 62% compared with the same period last year. However, it is essential to note that some analysts believe that part of this increase will become structural, i.e., a permanent feature on post-pandemic era shopping lists. Nevertheless, it is crucial to be aware that supplements claiming to boost the immune system aren’t always evidence-based and create a false sense of security.

## Scientific Deep-Dive
Turmeric is a spice and popular botanical product derived from the roots of the plant Curcuma longa found mostly in India and Southern Asia. Turmeric has an intense yellow color and distinct taste and is used as a dye as well as a spice in the preparation of curry. 
> **Scientific Research:** 
> Turmeric is a spice and popular botanical product derived from the roots of the plant Curcuma longa found mostly in India and Southern Asia. Turmeric has an intense yellow color and distinct taste and is used as a dye as well as a spice in the preparation of curry. Turmeric and curcumin are nonmutagenic and nongenotoxic. Oral use of turmeric is considered safe.

## Traditional Wisdom
Turmeric is a highly valued plant in Thailand, with a long history of use in traditional medicine. It is used to treat various diseases, such as stomach ulcers and constipation. The name "ขมิ้นชัน" is derived from the Thai words "ขมิ้น" meaning turmeric and "ชัน" meaning fragrant. The plant is commonly found in the northern regions of Thailand, particularly in Chiang Mai Province. The local community has a deep understanding of the plant's medicinal properties and uses it to treat various ailments. The community has established organizations to promote the use of traditional medicine, including the use of turmeric. Turmeric is also known as ขมิ้นชัน in Thai, and it is used to relieve stomach ulcers. The processing of turmeric involves boiling water.

## Safety, Regulatory, and Constraints
The active ingredient in turmeric is CURCUMA LONGA (TURMERIC) ROOT EXTRACT, and it is used to help prevent sunburn. However, skin cancer and skin aging can occur with sun exposure, and the product should only be used for external purposes. The product has been shown only to help prevent sunburn, not skin cancer or early skin aging. The warnings and directions for use include avoiding damaged or broken skin, stopping use if a rash occurs, and keeping the product out of eyes. The inactive ingredients in turmeric products may include MICA, CAMELLIA SINENSIS LEAF EXTRACT, CHLOROGENIC ACIDS, EUTERPE OLERACEA FRUIT EXTRACT, THEOBROMA CACAO (COCOA) SEED POWDER, VITIS VINIFERA (GRAPE) SEED EXTRACT, and others.

## Strategic Analysis and Product Opportunities
The COVID-19 pandemic has accelerated various wellness trends, including the use of superfoods that claim to boost immunity. Turmeric, in particular, has seen a significant increase in popularity, with US retail sales rising by 68% in the 14 weeks to June 6, compared to the same period last year. This trend suggests a market opportunity for developing new products that incorporate turmeric as a key ingredient, particularly those that cater to the growing demand for immune-boosting supplements. Although the Master Fact Sheet does not provide detailed Lab Facts on extraction methods, compounds identified, or pharmacological findings, it does mention that turmeric and curcumin are nonmutagenic and nongenotoxic, and oral use of turmeric is considered safe. However, the Safety Facts section provides warnings and directions for use, including avoiding damaged or broken skin, stopping use if a rash occurs, and keeping the product out of eyes. These constraints highlight the importance of careful product formulation, labeling, and user instructions to ensure safe and effective use. Based on the analysis of the Master Fact Sheet, a strategic recommendation for new product development would be to create a line of turmeric-based supplements and topical products that cater to the growing demand for immune-boosting and wellness products.

## Herbal Knowledge Summary
Curcuma longa, also known as turmeric, is a highly valued plant in Thailand, with a long history of use in traditional medicine. The importance of self-sufficiency in growing one's own herbs and the benefits of traditional Thai medicine are highlighted. According to the context, traditional Thai medicine can help reduce healthcare costs by treating minor ailments and can be used as an alternative to modern medicine for certain conditions. Turmeric has been used for healing in Thai wisdom for a long time. It has been used as a spice in Thai dishes and as a medicine to treat various health conditions. According to Thai wisdom, turmeric has a hot and spicy flavor that helps to stimulate digestion and relieve symptoms of indigestion and bloating. It is also believed to have anti-inflammatory properties that can help to reduce pain and inflammation in the body. Additionally, turmeric is thought to have antioxidant properties that can help to protect the body against free radicals and oxidative stress. In Thai cuisine, turmeric is often used in combination with other spices and herbs to create a flavorful and aromatic dish. It is also used as a natural food coloring and as an ingredient in traditional Thai medicine.

## Conclusion
In conclusion, turmeric is a highly valued plant in Thailand, with a long history of use in traditional medicine. The COVID-19 pandemic has accelerated various wellness trends, including the use of superfoods that claim to boost immunity. Turmeric, in particular, has seen a significant increase in popularity, with US retail sales rising by 68% in the 14 weeks to June 6, compared to the same period last year. Based on the analysis of the Master Fact Sheet, a strategic recommendation for new product development would be to create a line of turmeric-based supplements and topical products that cater to the growing demand for immune-boosting and wellness products. These products could be formulated to incorporate turmeric extract, curcumin, or other bioactive compounds, and could be positioned as natural, safe, and effective alternatives to existing products on the market.

# References
[1] Not found

# Sources Consulted
[1] https://globalwellnessinstitute.org/global-wellness-institute-blog/2020/07/14/accelerating-wellness-trends/
[2] https://www.ncbi.nlm.nih.gov/books/NBK548561/
[3] https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=3190768e-1a70-4021-8050-160e2910b9f8
[4] https://www.ncbi.nlm.nih.gov/books/NBK548561/
[5] https://www.sac.or.th/database/detail.aspx?ID=12345
"""

def test_markdown_conversion():
    """Test converting markdown to docx"""
    print("\n" + "="*70)
    print("UNIT TEST: Markdown to DOCX Conversion")
    print("="*70)
    
    # Create tool instance
    tool = SaveMarkdownToDocxTool()
    
    # Test with sample markdown
    output_file = "test_output.docx"
    
    print("\n Testing with sample markdown...")
    print("Input markdown length:", len(SAMPLE_MARKDOWN), "characters")
    print("First 200 chars:", SAMPLE_MARKDOWN[:200])
    
    # Run conversion
    result = tool._run(
        markdown_text=SAMPLE_MARKDOWN,
        output_file=output_file,
        research_topic="Turmeric Research Test"
    )
    
    print("\n" + "="*70)
    print("CONVERSION RESULT:")
    print("="*70)
    print(f"Success: {result['ok']}")
    print(f"Output: {result['path']}")
    print(f"Message: {result['message']}")
    
    if result['ok']:
        print("\n CONVERSION SUCCESSFUL!")
        print(f"File created: {output_file}")
        
        # Check if debug files were created
        debug_md = output_file.replace('.docx', '_debug.md')
        debug_html = output_file.replace('.docx', '_debug.html')
        
        if os.path.exists(debug_md):
            print(f"Debug markdown: {debug_md}")
            with open(debug_md, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"   - Length: {len(content)} chars")
                print(f"   - Has headings: {'##' in content or '#' in content}")
        
        if os.path.exists(debug_html):
            print(f"Debug HTML: {debug_html}")
            with open(debug_html, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"   - Length: {len(content)} chars")
                print(f"   - Has <h1> tags: {'<h1>' in content}")
                print(f"   - Has <h2> tags: {'<h2>' in content}")
                print(f"   - Still has markdown syntax: {'##' in content}")
        
        print("\n Now open test_output.docx to verify the formatting!")
        
    else:
        print("\n CONVERSION FAILED!")
        print("Check the error message above")
    
    return result

def test_with_file():
    """Test with actual markdown file if it exists"""
    print("\n" + "="*70)
    print("TESTING WITH ACTUAL FILE")
    print("="*70)
    
    # Check for markdown files
    test_files = [
        "task_13_20260123_224908.txt",
    ]
    
    found_file = None
    for f in test_files:
        if os.path.exists(f):
            found_file = f
            break
    
    if not found_file:
        print("No test markdown files found")
        print("   Looking for:", test_files)
        return None
    
    print(f"Found test file: {found_file}")
    
    # Read the file
    with open(found_file, 'r', encoding='utf-8') as f:
        markdown_text = f.read()
    
    print(f"   Length: {len(markdown_text)} characters")
    print(f"   First 300 chars: {markdown_text[:300]}")
    
    # Create tool and convert
    tool = SaveMarkdownToDocxTool()
    output_file = "test_from_file.docx"
    
    result = tool._run(
        markdown_text=markdown_text,
        output_file=output_file,
        research_topic="Turmeric: From Ancient Wisdom to Modern Strategy"
    )
    
    print("\n" + "="*70)
    print("RESULT:")
    print("="*70)
    print(f"Success: {result['ok']}")
    print(f"Message: {result['message']}")
    
    if result['ok']:
        print(f"\nSuccessfully created: {output_file}")
        print("💡 Open the file to check if headings are properly formatted")
    else:
        print(f"\nFailed: {result['message']}")
    
    return result

if __name__ == "__main__":
    print("\n Starting DOCX Conversion Tests...\n")
    
    # Test 1: Simple sample
    print("\n" + "TEST 1: Sample Markdown")
    test_markdown_conversion()
    
    # Test 2: Actual file if exists
    print("\n" + "TEST 2: Actual Markdown File")
    test_with_file()
    
    print("\n" + "="*70)
    print("TESTS COMPLETED")
    print("="*70)
    print("\nCheck the console output above to see where the problem is!")
    print("Look for these debug files:")
    print("  - test_output_debug.md")
    print("  - test_output_debug.html")
    print("  - test_from_file_debug.md")
    print("  - test_from_file_debug.html")