import os
import re
import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from document_parser import parse_file

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Synonym Dictionary for rule-based query expansion fallback
SUPPLY_CHAIN_SYNONYMS = {
    "stock": ["inventory", "quantity", "on hand", "warehouse", "sku", "units", "items"],
    "inventory": ["stock", "quantity", "on hand", "warehouse", "sku", "units", "items"],
    "delay": ["late", "delayed", "transit", "stuck", "estimated delivery", "shipping", "carrier", "customs"],
    "late": ["delay", "delayed", "transit", "stuck", "estimated delivery", "shipping", "carrier", "customs"],
    "shipment": ["shipping", "log", "po", "purchase order", "carrier", "transit", "delivery"],
    "delivery": ["shipment", "shipping", "log", "po", "purchase order", "carrier", "transit", "delivered"],
    "sla": ["penalty", "contract", "terms", "agreement", "rules", "policy", "non-compliance"],
    "penalty": ["sla", "fine", "charge", "deducted", "fee", "non-compliance", "rejection"],
    "supplier": ["vendor", "contact", "sla", "scantech", "ironclad", "voltbright", "paperco", "tracetags", "supplier xyz"],
    "vendor": ["supplier", "contact", "sla", "scantech", "ironclad", "voltbright", "paperco", "tracetags", "supplier xyz"]
}

class AdvancedRAGEngine:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.chunks = []
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.dense_vectorizer = None
        self.dense_embeddings = None
        self.reindex_all()

    def set_api_key(self, api_key):
        global GEMINI_API_KEY
        GEMINI_API_KEY = api_key
        self.reindex_all()

    def get_api_key(self):
        return GEMINI_API_KEY

    def reindex_all(self):
        """Finds all supported files in the data directory, parses them using parent-child chunking, and builds indices."""
        self.chunks = []
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        files = [os.path.join(self.data_dir, f) for f in os.listdir(self.data_dir) 
                 if os.path.isfile(os.path.join(self.data_dir, f)) and not f.startswith('.')]
                 
        for file_path in files:
            file_chunks = parse_file(file_path)
            self.chunks.extend(file_chunks)
            
        print(f"Total chunks indexed: {len(self.chunks)}")
        
        if not self.chunks:
            self.tfidf_matrix = None
            self.dense_embeddings = None
            return
            
        # Build Lexical/Sparse Index
        corpus = [chunk["text"] for chunk in self.chunks]
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
        
        # Build Dense Index
        self._build_dense_index(corpus)

    def _build_dense_index(self, corpus):
        if GEMINI_API_KEY:
            try:
                embeddings = []
                batch_size = 50
                for i in range(0, len(corpus), batch_size):
                    batch = corpus[i:i+batch_size]
                    batch_embs = self._get_gemini_embeddings(batch)
                    embeddings.extend(batch_embs)
                self.dense_embeddings = np.array(embeddings)
                print("Dense index built successfully using Gemini API.")
                return
            except Exception as e:
                print(f"Failed to build Gemini embeddings: {e}. Falling back to local dense approximation.")
        
        # Fallback local char n-gram dense approximation
        self.dense_vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5))
        self.dense_embeddings = self.dense_vectorizer.fit_transform(corpus).toarray()
        print("Dense index built successfully using Local Character N-gram approximation.")

    def _get_gemini_embeddings(self, texts):
        embeddings = []
        for text in texts:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"
            payload = {
                "model": "models/text-embedding-004",
                "content": {
                    "parts": [{"text": text}]
                }
            }
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            embeddings.append(res.json()["embedding"]["values"])
        return embeddings

    def _get_query_embedding(self, query):
        if GEMINI_API_KEY and self.dense_embeddings is not None:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"
                payload = {
                    "model": "models/text-embedding-004",
                    "content": {
                        "parts": [{"text": query}]
                    }
                }
                res = requests.post(url, json=payload, timeout=10)
                res.raise_for_status()
                return np.array(res.json()["embedding"]["values"])
            except Exception as e:
                print(f"Failed to embed query: {e}. Falling back to local vectorizer.")
                
        if self.dense_vectorizer is not None:
            return self.dense_vectorizer.transform([query]).toarray()[0]
        return None

    def rewrite_query_with_history(self, query, history_messages):
        """Uses Gemini or basic rules to rewrite follow-up questions to be self-contained."""
        if not history_messages:
            return query
            
        # Fast local skip: if the query doesn't look like a pronoun-heavy follow-up,
        # we can skip rewriting to save LLM call latency.
        q_lower = query.lower()
        pronouns = ["it", "they", "them", "these", "those", "that", "this", "him", "her", "he", "she"]
        has_pronoun = any(f" {p} " in f" {q_lower} " or q_lower.startswith(p) or q_lower.endswith(p) for p in pronouns)
        
        if not has_pronoun:
            return query
            
        if GEMINI_API_KEY:
            try:
                chat_context = ""
                for msg in history_messages[-4:]:
                    chat_context += f"{msg['role']}: {msg['content']}\n"
                
                prompt = (
                    "Given the following conversation history and a follow-up question, rewrite the follow-up question to be a self-contained, independent query search query. "
                    "Do NOT answer the question, just return the rewritten question string.\n\n"
                    f"HISTORY:\n{chat_context}"
                    f"FOLLOW-UP: {query}\n\n"
                    "REWRITTEN QUERY:"
                )
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                res = requests.post(url, json=payload, timeout=10)
                res.raise_for_status()
                rewritten = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if rewritten:
                    print(f"Rewrote query from '{query}' to '{rewritten}' using Gemini")
                    return rewritten
            except Exception as e:
                print(f"Gemini query rewrite failed: {e}. Using rules.")
                
        # Basic heuristic query rewriting
        q_lower = query.lower()
        pronouns = ["it", "them", "they", "its", "their", "that", "this", "him", "her"]
        has_pronoun = any(f" {p} " in f" {q_lower} " or q_lower.startswith(f"{p} ") for p in pronouns)
        
        if has_pronoun and len(history_messages) >= 2:
            # Find last product SKU or supplier name in history
            last_user_query = history_messages[-2]['content']
            skus = re.findall(r'\b[P|p]\d{3}\b|\bPROD-\w+\b', last_user_query)
            if skus:
                # Replace pronouns or append context
                return f"{query} (referring to product {skus[0]})"
            
            # Simple concatenation fallback
            return f"{query} (based on: {last_user_query})"
            
        return query

    def query_expansion(self, original_query):
        """Expands the query using local rule-based supply chain synonyms for speed."""
        # Local Synonym-based expansion (Instant response, saves 1 LLM call and 2 embedding calls)
        variations = [original_query]
        words = re.findall(r'\b\w+\b', original_query.lower())
        expansion_terms = []
        for w in words:
            if w in SUPPLY_CHAIN_SYNONYMS:
                expansion_terms.extend(SUPPLY_CHAIN_SYNONYMS[w][:2])
                
        if expansion_terms:
            unique_terms = list(set(expansion_terms))
            variations.append(f"{original_query} {' '.join(unique_terms[:3])}")
            variations.append(f"operational logs: {' and '.join(unique_terms[:2])} details")
        else:
            variations.append(f"retail logistics {original_query}")
            variations.append(f"operational reports matching {original_query}")
            
        return [v.strip() for v in variations[:3]]

        # Local Synonym-based expansion
        variations = [original_query]
        words = re.findall(r'\b\w+\b', original_query.lower())
        expansion_terms = []
        for w in words:
            if w in SUPPLY_CHAIN_SYNONYMS:
                expansion_terms.extend(SUPPLY_CHAIN_SYNONYMS[w][:2])
                
        if expansion_terms:
            unique_terms = list(set(expansion_terms))
            variations.append(f"{original_query} {' '.join(unique_terms[:3])}")
            variations.append(f"operational logs: {' and '.join(unique_terms[:2])} details")
        else:
            variations.append(f"retail logistics {original_query}")
            variations.append(f"operational reports matching {original_query}")
            
        return [v.strip() for v in variations[:3]]

    def search_sparse(self, query, valid_indices=None, top_n=10):
        if self.tfidf_matrix is None or self.tfidf_vectorizer is None:
            return []
            
        q_vec = self.tfidf_vectorizer.transform([query])
        similarities = cosine_similarity(q_vec, self.tfidf_matrix).flatten()
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices:
            if valid_indices is not None and idx not in valid_indices:
                continue
            score = float(similarities[idx])
            if score > 0.0:
                results.append((idx, score))
            if len(results) >= top_n:
                break
        return results

    def search_dense(self, query, valid_indices=None, top_n=10):
        if self.dense_embeddings is None:
            return []
            
        q_emb = self._get_query_embedding(query)
        if q_emb is None:
            return []
            
        if GEMINI_API_KEY and len(q_emb.shape) == 1:
            norms = np.linalg.norm(self.dense_embeddings, axis=1)
            q_norm = np.linalg.norm(q_emb)
            if q_norm == 0 or np.any(norms == 0):
                similarities = np.zeros(len(self.dense_embeddings))
            else:
                similarities = np.dot(self.dense_embeddings, q_emb) / (norms * q_norm)
        else:
            q_vec = q_emb.reshape(1, -1)
            similarities = cosine_similarity(q_vec, self.dense_embeddings).flatten()
            
        top_indices = np.argsort(similarities)[::-1]
        results = []
        for idx in top_indices:
            if valid_indices is not None and idx not in valid_indices:
                continue
            score = float(similarities[idx])
            # Threshold to filter noise
            if score > 0.05:
                results.append((idx, score))
            if len(results) >= top_n:
                break
        return results

    def reciprocal_rank_fusion(self, sparse_results, dense_results, k=60):
        rrf_scores = {}
        for rank, (idx, _) in enumerate(sparse_results):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
        for rank, (idx, _) in enumerate(dense_results):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
            
        return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    def retrieve(self, query, top_k=5, filters=None):
        """Implements Advanced Retrieval (Metadata Filtering -> Expansion -> Hybrid Search -> RRF -> Re-ranking)."""
        if not self.chunks:
            return [], []
            
        # 1. Apply Metadata Filters
        valid_indices = None
        if filters:
            valid_indices = set()
            for idx, chunk in enumerate(self.chunks):
                match = True
                for key, val in filters.items():
                    if not val:
                        continue
                    meta_val = chunk["metadata"].get(key)
                    if not meta_val:
                        match = False
                        break
                    if isinstance(meta_val, list):
                        if str(val) not in [str(x) for x in meta_val]:
                            match = False
                            break
                    elif str(val).lower() not in str(meta_val).lower():
                        match = False
                        break
                if match:
                    valid_indices.add(idx)
                    
            if not valid_indices:
                return [], {"original_query": query, "expanded_queries": [query], "sparse_results": [], "dense_results": [], "rrf_results": []}

        # 2. Query Expansion
        expanded_queries = self.query_expansion(query)
        
        all_sparse_runs = []
        all_dense_runs = []
        
        # 3. Hybrid Search
        for eq in expanded_queries:
            all_sparse_runs.extend(self.search_sparse(eq, valid_indices=valid_indices, top_n=10))
            all_dense_runs.extend(self.search_dense(eq, valid_indices=valid_indices, top_n=10))
            
        # Deduplicate results keeping max score per chunk
        def dedup_and_sort(run):
            best_scores = {}
            for idx, score in run:
                if idx not in best_scores or score > best_scores[idx]:
                    best_scores[idx] = score
            return sorted(best_scores.items(), key=lambda x: x[1], reverse=True)
            
        sparse_best = dedup_and_sort(all_sparse_runs)
        dense_best = dedup_and_sort(all_dense_runs)
        
        # 4. RRF
        rrf_ranks = self.reciprocal_rank_fusion(sparse_best, dense_best)
        
        # 5. Re-ranking / Selection (Top K Chunks)
        retrieved_chunks = []
        for chunk_idx, rrf_score in rrf_ranks[:top_k]:
            chunk_data = self.chunks[chunk_idx].copy()
            chunk_data["rrf_score"] = float(rrf_score)
            chunk_data["sparse_score"] = float(next((score for idx, score in sparse_best if idx == chunk_idx), 0.0))
            chunk_data["dense_score"] = float(next((score for idx, score in dense_best if idx == chunk_idx), 0.0))
            retrieved_chunks.append(chunk_data)
            
        # Packing trace details
        trace = {
            "original_query": query,
            "expanded_queries": expanded_queries,
            "sparse_results": [
                {"chunk_text": self.chunks[idx]["text"][:100] + "...", "source": self.chunks[idx]["metadata"]["source"], "score": score} 
                for idx, score in sparse_best[:5]
            ],
            "dense_results": [
                {"chunk_text": self.chunks[idx]["text"][:100] + "...", "source": self.chunks[idx]["metadata"]["source"], "score": score} 
                for idx, score in dense_best[:5]
            ],
            "rrf_results": [
                {"chunk_text": chunk_data["text"][:100] + "...", "source": chunk_data["metadata"]["source"], "rrf_score": chunk_data["rrf_score"]} 
                for chunk_data in retrieved_chunks
            ]
        }
        
        return retrieved_chunks, trace

    def generate_response(self, query, context_chunks):
        if not context_chunks:
            return "No reference materials found in operational documents matching your criteria. Please upload relevant files or adjust filters."
            
        # Implement Parent-Child Context Expansion in generative phase
        # Map child chunks to parent_text and deduplicate parent texts
        parent_texts = []
        seen_parents = set()
        for chunk in context_chunks:
            parent_txt = chunk["metadata"].get("parent_text", chunk["text"])
            if parent_txt not in seen_parents:
                seen_parents.add(parent_txt)
                parent_texts.append(f"[Source: {chunk['metadata']['source']}]: {parent_txt}")
                
        context_text = "\n\n".join(parent_texts)
        
        if GEMINI_API_KEY:
            try:
                system_instruction = (
                    "You are a professional Enterprise Retail Operations & Supply Chain AI Assistant. "
                    "You have access to current inventory levels, purchase orders, shipping records, and supplier SLA terms. "
                    "Answer the user's questions truthfully and precisely using the provided context. "
                    "Always cite the source document name (e.g. 'q3_sla_review.pdf') when referencing facts. "
                    "If the answer cannot be found in the context, politely explain what you know and suggest checking other documents. "
                    "Keep responses highly structured, utilizing tables, bullet points, and headers."
                )
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": f"{system_instruction}\n\nCONTEXT:\n{context_text}\n\nQUESTION: {query}"
                        }]
                    }]
                }
                res = requests.post(url, json=payload, timeout=25)
                res.raise_for_status()
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print(f"Gemini generation failed: {e}. Using fallback.")
                
        return self._smart_local_generator(query, context_chunks)

    def _smart_local_generator(self, query, chunks):
        q_lower = query.lower()
        response_lines = [
            "💡 *[Demo Mode - Heuristic RAG Response]*",
            "*(Connect a Gemini API key to activate natural language summaries)*\n"
        ]
        
        is_inventory = any(w in q_lower for w in ["stock", "inventory", "reorder", "quantity", "low", "sku"])
        is_sla = any(w in q_lower for w in ["sla", "penalty", "late", "fee", "agreement", "rules"])
        is_shipping = any(w in q_lower for w in ["shipping", "transit", "carrier", "delay", "po"])
        
        matched = False
        if is_inventory:
            matched = True
            response_lines.append("### 📦 Inventory Status Heuristics")
            items = []
            for c in chunks:
                if c["metadata"].get("type") == "csv" and "data" in c["metadata"]:
                    items.append(c["metadata"]["data"])
            if items:
                for item in items[:4]:
                    response_lines.append(
                        f"- **{item.get('Product Name')}** ({item.get('SKU')}): "
                        f"Stock {item.get('Current Stock')} / Reorder: {item.get('Reorder Threshold')} "
                        f"({item.get('Warehouse Location', 'N/A')})."
                    )
            else:
                response_lines.append("No structured CSV inventory items matched.")
                
        if is_sla:
            matched = True
            response_lines.append("### 📜 SLA & Policies Details")
            for c in chunks:
                if "sla" in c["text"].lower() or "penalty" in c["text"].lower() or "agreement" in c["text"].lower():
                    snippet = c["metadata"].get("parent_text", c["text"])[:350] + "..."
                    response_lines.append(f"> *Source: {c['metadata']['source']}*\n> {snippet}\n")
                    
        if is_shipping:
            matched = True
            response_lines.append("### 🚚 Log & Shipments Status")
            shipments = []
            for c in chunks:
                if c["metadata"].get("type") == "csv" and "Carrier" in c["text"]:
                    shipments.append(c["metadata"]["data"])
            if shipments:
                for s in shipments[:4]:
                    response_lines.append(f"- **PO {s.get('Purchase Order')}** ({s.get('SKU')}): Carrier {s.get('Carrier')} -> {s.get('Status')} ({s.get('Notes')})")
            else:
                response_lines.append("No logistics files matching shipping records found in context.")
                
        if not matched:
            response_lines.append("### 🔎 Document Context Extracts")
            for idx, c in enumerate(chunks[:3]):
                text_show = c["metadata"].get("parent_text", c["text"])[:300] + "..."
                response_lines.append(f"**Source {idx+1}: {c['metadata']['source']}**")
                response_lines.append(f"> {text_show}\n")
                
        return "\n".join(response_lines)
