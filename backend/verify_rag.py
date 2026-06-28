import os
import sys

# Ensure stdout handles UTF-8 (emojis, etc.) properly in Windows command prompt
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from rag_engine import AdvancedRAGEngine

def test_rag_pipeline():
    print("=== Testing Advanced Retail RAG Engine Verification ===")
    
    # 1. Initialize engine
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    print(f"Loading documents from: {data_dir}")
    
    engine = AdvancedRAGEngine(data_dir=data_dir)
    
    # Check that chunks exist
    chunk_count = len(engine.chunks)
    print(f"Successfully loaded and chunked documents. Total chunks: {chunk_count}")
    assert chunk_count > 0, "No chunks were indexed!"
    
    # 2. Test Query Expansion
    test_query = "Low stock barcode scanner"
    expanded = engine.query_expansion(test_query)
    print(f"\nTest Query: '{test_query}'")
    print(f"Expanded Queries: {expanded}")
    assert len(expanded) > 1, "Query expansion failed to produce variations!"
    
    # 3. Test Retrieval with RRF
    print("\nExecuting Hybrid Retrieval with RRF...")
    retrieved_chunks, trace = engine.retrieve(test_query, top_k=3)
    
    print(f"Retrieved {len(retrieved_chunks)} chunks.")
    assert len(retrieved_chunks) > 0, "Retrieval returned 0 chunks!"
    
    print("\nTop 3 Retrieved Chunks (Sorted by RRF Score):")
    for i, c in enumerate(retrieved_chunks):
        print(f"Rank {i+1} [RRF Score: {c['rrf_score']:.4f}] from Source: {c['metadata']['source']}")
        print(f"Text Snippet: {c['text'][:120]}...\n")
        
    # Check trace outputs
    assert "expanded_queries" in trace, "Trace is missing query expansions!"
    assert "sparse_results" in trace, "Trace is missing sparse results!"
    assert "dense_results" in trace, "Trace is missing dense results!"
    assert "rrf_results" in trace, "Trace is missing RRF scores!"
    
    # 4. Test Local Generation Fallback
    print("Testing response generator...")
    response = engine.generate_response(test_query, retrieved_chunks)
    print(f"\nGenerated Response:\n{response}")
    
    print("\n==============================================")
    print("🎉 Advanced RAG Pipeline verification PASSED!")
    print("==============================================")

if __name__ == "__main__":
    test_rag_pipeline()
