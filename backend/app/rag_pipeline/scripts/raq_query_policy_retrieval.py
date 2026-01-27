# # rag_query_construction.py
# """
# RAG Query Construction for Prior Authorization Policy Retrieval
# Optimized for retrieving relevant insurance policy criteria
# """

# from typing import Dict, List, Optional
# from dataclasses import dataclass
# from datetime import datetime


# @dataclass
# class RAGQuery:
#     """Structured RAG query with semantic text and metadata filters"""
#     semantic_query: str
#     metadata_filters: Dict
#     top_k: int = 10
#     score_threshold: float = 0.70
#     rerank: bool = True


# class PolicyQueryBuilder:
#     """
#     Constructs optimized RAG queries for insurance policy retrieval.
    
#     Strategy:
#     1. Use hybrid search: semantic query + metadata filters
#     2. Multiple query variations for better recall
#     3. Contextual enrichment using clinical evidence
#     """
    
#     def __init__(self, evidence: Dict):
#         """
#         Args:
#             evidence: Extracted clinical evidence JSON
#         """
#         self.evidence = evidence
        
#     def build_primary_query(self) -> RAGQuery:
#         """
#         Primary query - most specific, targets exact policy match
        
#         Example:
#         "Aetna prior authorization MRI knee CPT 73721 medically necessary criteria"
#         """
#         payer = self.evidence['insurance']['payer']
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
#         procedure_desc = self.evidence['requested_procedure']['description']
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
        
#         # Construct semantic query
#         semantic_query = (
#             f"{payer} prior authorization {procedure_desc} "
#             f"{body_part} CPT {cpt_code} "
#             f"medically necessary criteria requirements"
#         )
        
#         # Metadata filters for precise matching
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=8,
#             score_threshold=0.75
#         )
    
#     def build_diagnosis_specific_query(self) -> RAGQuery:
#         """
#         Query targeting diagnosis-specific criteria
        
#         Example:
#         "Aetna knee MRI meniscal tear M23.201 coverage criteria"
#         """
#         payer = self.evidence['insurance']['payer']
#         diagnosis_code = self.evidence['diagnosis']['primary_diagnosis']
#         diagnosis_desc = self.evidence['diagnosis'].get('primary_description', '')
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
        
#         # Extract key diagnosis terms (e.g., "meniscal tear" from description)
#         diagnosis_keywords = self._extract_diagnosis_keywords(diagnosis_desc)
        
#         semantic_query = (
#             f"{payer} {body_part} MRI {diagnosis_keywords} "
#             f"{diagnosis_code} coverage criteria requirements"
#         )
        
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#             "subcategory": "diagnosis_requirements"  # Target specific section
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=5,
#             score_threshold=0.70
#         )
    
#     def build_conservative_treatment_query(self) -> RAGQuery:
#         """
#         Query targeting conservative treatment requirements
        
#         Example:
#         "Aetna knee MRI conservative treatment physical therapy requirements duration"
#         """
#         payer = self.evidence['insurance']['payer']
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
        
#         # Check what conservative treatments were attempted
#         conservative_care = self.evidence.get('conservative_treatment', {})
#         treatment_types = []
#         if conservative_care.get('physical_therapy', {}).get('completed'):
#             treatment_types.append('physical therapy')
#         if conservative_care.get('medications', {}).get('nsaids'):
#             treatment_types.append('NSAIDs medication')
        
#         treatments_str = ' '.join(treatment_types) if treatment_types else 'conservative treatment'
        
#         semantic_query = (
#             f"{payer} {body_part} MRI conservative treatment requirements "
#             f"{treatments_str} duration minimum weeks criteria"
#         )
        
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#             "subcategory": {"$in": ["conservative_treatment", "pt_requirements", "medication_requirements"]}
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=6,
#             score_threshold=0.70
#         )
    
#     def build_clinical_findings_query(self) -> RAGQuery:
#         """
#         Query targeting required clinical findings/exam criteria
        
#         Example:
#         "Aetna MRI knee clinical findings McMurray test joint line tenderness required"
#         """
#         payer = self.evidence['insurance']['payer']
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
        
#         # Extract positive clinical findings from evidence
#         clinical_findings = self.evidence.get('clinical_findings', {})
#         exam = clinical_findings.get('physical_exam', {})
        
#         positive_findings = []
#         if exam.get('mcmurray_test', '').startswith('positive'):
#             positive_findings.append('McMurray test')
#         if exam.get('lachman_test') == 'positive':
#             positive_findings.append('Lachman test')
#         if exam.get('joint_line_tenderness'):
#             positive_findings.append('joint line tenderness')
#         if exam.get('effusion'):
#             positive_findings.append('effusion')
        
#         findings_str = ' '.join(positive_findings[:3])  # Limit to top 3
        
#         semantic_query = (
#             f"{payer} MRI {body_part} clinical findings examination "
#             f"{findings_str} required criteria documentation"
#         )
        
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#             "subcategory": "clinical_findings"
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=5,
#             score_threshold=0.70
#         )
    
#     def build_exception_query(self) -> RAGQuery:
#         """
#         Query targeting policy exceptions (e.g., acute trauma, red flags)
        
#         Example:
#         "Aetna MRI knee exceptions acute trauma ligament rupture conservative treatment waived"
#         """
#         payer = self.evidence['insurance']['payer']
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
        
#         # Check for red flags that might trigger exceptions
#         red_flags = self.evidence.get('red_flags', {})
#         exception_terms = []
        
#         if red_flags.get('acute_trauma'):
#             exception_terms.append('acute trauma')
#         if red_flags.get('unable_to_bear_weight'):
#             exception_terms.append('unable to bear weight')
#         if red_flags.get('locked_knee'):
#             exception_terms.append('locked knee')
#         if red_flags.get('suspected_fracture'):
#             exception_terms.append('suspected fracture')
        
#         # Also check diagnosis for ligament injuries
#         diagnosis = self.evidence['diagnosis']['primary_diagnosis']
#         if diagnosis.startswith('S83.5') or diagnosis.startswith('S83.6'):
#             exception_terms.append('ligament rupture')
        
#         exceptions_str = ' '.join(exception_terms) if exception_terms else 'exceptions waiver'
        
#         semantic_query = (
#             f"{payer} MRI {body_part} exceptions {exceptions_str} "
#             f"conservative treatment waived criteria"
#         )
        
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#             "subcategory": {"$in": ["treatment_exceptions", "exceptions"]}
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=4,
#             score_threshold=0.65  # Lower threshold for exceptions
#         )
    
#     def build_imaging_requirements_query(self) -> RAGQuery:
#         """
#         Query targeting prior imaging requirements (X-ray, previous MRI, etc.)
        
#         Example:
#         "Aetna MRI knee x-ray requirement prior imaging timeframe"
#         """
#         payer = self.evidence['insurance']['payer']
#         body_part = self.evidence['requested_procedure'].get('body_part', '')
#         cpt_code = self.evidence['requested_procedure']['cpt_code']
        
#         semantic_query = (
#             f"{payer} MRI {body_part} x-ray requirement "
#             f"prior imaging timeframe days criteria"
#         )
        
#         metadata_filters = {
#             "payer": payer.lower(),
#             "cpt_code": cpt_code,
#             "subcategory": "imaging_requirements"
#         }
        
#         return RAGQuery(
#             semantic_query=semantic_query,
#             metadata_filters=metadata_filters,
#             top_k=3,
#             score_threshold=0.70
#         )
    
#     def build_all_queries(self) -> List[RAGQuery]:
#         """
#         Build comprehensive query set for maximum policy coverage.
        
#         Returns queries in priority order:
#         1. Primary (general requirements)
#         2. Diagnosis-specific
#         3. Conservative treatment
#         4. Clinical findings
#         5. Exceptions (if applicable)
#         6. Imaging requirements
#         """
#         queries = [
#             self.build_primary_query(),
#             self.build_diagnosis_specific_query(),
#             self.build_conservative_treatment_query(),
#             self.build_clinical_findings_query(),
#             self.build_imaging_requirements_query()
#         ]
        
#         # Only add exception query if red flags present
#         red_flags = self.evidence.get('red_flags', {})
#         if any(red_flags.values()):
#             queries.append(self.build_exception_query())
        
#         return queries
    
#     def _extract_diagnosis_keywords(self, diagnosis_description: str) -> str:
#         """
#         Extract key clinical terms from diagnosis description.
        
#         Example: "Derangement of medial meniscus due to tear" -> "meniscal tear"
#         """
#         if not diagnosis_description:
#             return ""
        
#         # Common patterns to extract
#         keywords_map = {
#             'meniscus': 'meniscal tear',
#             'ligament': 'ligament injury',
#             'osteoarthritis': 'osteoarthritis',
#             'fracture': 'fracture',
#             'dislocation': 'dislocation',
#             'cartilage': 'cartilage damage',
#             'tendon': 'tendon injury'
#         }
        
#         description_lower = diagnosis_description.lower()
#         for key, value in keywords_map.items():
#             if key in description_lower:
#                 return value
        
#         # Fallback: return first 3 words after stripping common terms
#         words = diagnosis_description.lower().replace('unspecified', '').split()
#         return ' '.join(words[:3])


# # =============================================================================
# # RAG RETRIEVAL ENGINE
# # =============================================================================

# class PolicyRetriever:
#     """
#     Executes RAG queries against vector database and aggregates results.
#     Handles deduplication, ranking, and result merging.
#     """
    
#     def __init__(self, vector_db):
#         """
#         Args:
#             vector_db: Vector database instance (e.g., Pinecone, Weaviate, Chroma)
#         """
#         self.vector_db = vector_db
    
#     def retrieve_multi_query(
#         self, 
#         queries: List[RAGQuery],
#         deduplicate: bool = True,
#         max_total_chunks: int = 15
#     ) -> List[Dict]:
#         """
#         Execute multiple queries and aggregate results.
        
#         Strategy:
#         1. Run all queries in parallel
#         2. Deduplicate by chunk_id
#         3. Re-rank by relevance score
#         4. Return top N chunks
        
#         Args:
#             queries: List of RAGQuery objects
#             deduplicate: Remove duplicate chunks
#             max_total_chunks: Maximum chunks to return
            
#         Returns:
#             List of retrieved chunks with metadata
#         """
#         all_chunks = []
#         seen_chunk_ids = set()
        
#         for query in queries:
#             # Execute query against vector DB
#             results = self._execute_query(query)
            
#             for chunk in results:
#                 chunk_id = chunk.get('chunk_id') or chunk.get('id')
                
#                 # Deduplicate
#                 if deduplicate and chunk_id in seen_chunk_ids:
#                     continue
                
#                 seen_chunk_ids.add(chunk_id)
                
#                 # Add query context for debugging
#                 chunk['retrieved_by_query'] = query.semantic_query
#                 all_chunks.append(chunk)
        
#         # Re-rank by score
#         all_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
        
#         # Return top N
#         return all_chunks[:max_total_chunks]
    
#     def _execute_query(self, query: RAGQuery) -> List[Dict]:
#         """
#         Execute single query against vector database.
        
#         This is a template - adapt to your specific vector DB client.
#         Examples provided for: Pinecone, Chroma, Weaviate
#         """
        
#         # OPTION 1: Pinecone
#         # results = self.vector_db.query(
#         #     query.semantic_query,
#         #     filter=query.metadata_filters,
#         #     top_k=query.top_k,
#         #     include_metadata=True
#         # )
#         # return [
#         #     {
#         #         'chunk_id': match['id'],
#         #         'text': match['metadata']['text'],
#         #         'score': match['score'],
#         #         'metadata': match['metadata']
#         #     }
#         #     for match in results['matches']
#         #     if match['score'] >= query.score_threshold
#         # ]
        
#         # OPTION 2: ChromaDB
#         # results = self.vector_db.query(
#         #     query_texts=[query.semantic_query],
#         #     where=query.metadata_filters,
#         #     n_results=query.top_k
#         # )
#         # return [
#         #     {
#         #         'chunk_id': results['ids'][0][i],
#         #         'text': results['documents'][0][i],
#         #         'score': 1 - results['distances'][0][i],  # Convert distance to similarity
#         #         'metadata': results['metadatas'][0][i]
#         #     }
#         #     for i in range(len(results['ids'][0]))
#         #     if (1 - results['distances'][0][i]) >= query.score_threshold
#         # ]
        
#         # OPTION 3: Weaviate
#         # results = self.vector_db.query.get(
#         #     class_name="PolicyChunk",
#         #     properties=["text", "chunk_id", "payer", "cpt_code", "page"]
#         # ).with_near_text({
#         #     "concepts": [query.semantic_query]
#         # }).with_where({
#         #     "operator": "And",
#         #     "operands": [
#         #         {"path": [k], "operator": "Equal", "valueString": v}
#         #         for k, v in query.metadata_filters.items()
#         #     ]
#         # }).with_limit(query.top_k).do()
        
#         # PLACEHOLDER for demonstration
#         return []
    
#     def retrieve_with_fallback(
#         self,
#         evidence: Dict,
#         primary_only: bool = False
#     ) -> List[Dict]:
#         """
#         Main retrieval method with fallback strategy.
        
#         Strategy:
#         1. Try primary query first
#         2. If insufficient results (<5 chunks), expand to all queries
#         3. If still insufficient, lower score threshold
        
#         Args:
#             evidence: Clinical evidence JSON
#             primary_only: Only use primary query (faster, less comprehensive)
            
#         Returns:
#             Retrieved policy chunks
#         """
#         query_builder = PolicyQueryBuilder(evidence)
        
#         # Attempt 1: Primary query only
#         primary_query = query_builder.build_primary_query()
#         chunks = self._execute_query(primary_query)
        
#         if len(chunks) >= 5 or primary_only:
#             return chunks[:15]
        
#         # Attempt 2: Multi-query retrieval
#         print(f"Primary query returned {len(chunks)} chunks. Expanding to multi-query...")
#         all_queries = query_builder.build_all_queries()
#         chunks = self.retrieve_multi_query(all_queries, max_total_chunks=15)
        
#         if len(chunks) >= 5:
#             return chunks
        
#         # Attempt 3: Lower threshold and retry
#         print(f"Multi-query returned {len(chunks)} chunks. Lowering threshold...")
#         for query in all_queries:
#             query.score_threshold = 0.60  # Lower threshold
        
#         chunks = self.retrieve_multi_query(all_queries, max_total_chunks=15)
        
#         return chunks


# # =============================================================================
# # EXAMPLE USAGE
# # =============================================================================

# def example_usage():
#     """Demonstrate query construction and retrieval"""
    
#     # Load mock evidence
#     import json
#     with open('mock_data/expected_outputs/chart_001_evidence.json', 'r') as f:
#         evidence = json.load(f)
    
#     # Build queries
#     query_builder = PolicyQueryBuilder(evidence)
    
#     print("=" * 80)
#     print("RAG QUERY EXAMPLES")
#     print("=" * 80)
    
#     # Primary query
#     primary = query_builder.build_primary_query()
#     print("\n1. PRIMARY QUERY:")
#     print(f"   Semantic: {primary.semantic_query}")
#     print(f"   Filters: {primary.metadata_filters}")
#     print(f"   Top-K: {primary.top_k}")
    
#     # Diagnosis query
#     diagnosis = query_builder.build_diagnosis_specific_query()
#     print("\n2. DIAGNOSIS-SPECIFIC QUERY:")
#     print(f"   Semantic: {diagnosis.semantic_query}")
#     print(f"   Filters: {diagnosis.metadata_filters}")
    
#     # Conservative treatment query
#     treatment = query_builder.build_conservative_treatment_query()
#     print("\n3. CONSERVATIVE TREATMENT QUERY:")
#     print(f"   Semantic: {treatment.semantic_query}")
#     print(f"   Filters: {treatment.metadata_filters}")
    
#     # Clinical findings query
#     clinical = query_builder.build_clinical_findings_query()
#     print("\n4. CLINICAL FINDINGS QUERY:")
#     print(f"   Semantic: {clinical.semantic_query}")
#     print(f"   Filters: {clinical.metadata_filters}")
    
#     # Exception query (if applicable)
#     exception = query_builder.build_exception_query()
#     print("\n5. EXCEPTION QUERY:")
#     print(f"   Semantic: {exception.semantic_query}")
#     print(f"   Filters: {exception.metadata_filters}")
    
#     # Imaging requirements query
#     imaging = query_builder.build_imaging_requirements_query()
#     print("\n6. IMAGING REQUIREMENTS QUERY:")
#     print(f"   Semantic: {imaging.semantic_query}")
#     print(f"   Filters: {imaging.metadata_filters}")
    
#     print("\n" + "=" * 80)
#     print("All queries constructed successfully!")
#     print("=" * 80)
    
#     # Show how to use with retriever (pseudo-code)
#     print("\n" + "=" * 80)
#     print("RETRIEVAL USAGE EXAMPLE:")
#     print("=" * 80)
#     print("""
#     # Initialize your vector DB client
#     vector_db = ChromaDB(...)  # or Pinecone, Weaviate, etc.
    
#     # Create retriever
#     retriever = PolicyRetriever(vector_db)
    
#     # Retrieve policy chunks
#     chunks = retriever.retrieve_with_fallback(evidence)
    
#     # chunks will contain:
#     # [
#     #   {
#     #     'chunk_id': 'aetna_knee_001',
#     #     'text': 'MRI of the knee is considered MEDICALLY NECESSARY...',
#     #     'score': 0.89,
#     #     'metadata': {'payer': 'aetna', 'cpt_code': '73721', ...},
#     #     'retrieved_by_query': 'aetna prior authorization MRI...'
#     #   },
#     #   ...
#     # ]
#     """)


# if __name__ == "__main__":
#     example_usage()