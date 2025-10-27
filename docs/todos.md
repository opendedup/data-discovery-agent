# Data Discovery Agent - TODOs

## Improve Discovery JOIN Validation

### Problem

The data discovery agent currently returns datasets that may not have compatible JOIN keys, leading to queries that return 0 rows during query generation. This wastes LLM tokens and processing time on refinement attempts that are unlikely to succeed.

### Current Behavior

- Discovery returns tables based on content relevance to the insight
- No validation of whether tables can actually be joined together
- Query generation agent attempts to JOIN tables that may lack compatible keys
- Results in queries with 0 rows, triggering expensive refinement loops

### Proposed Solution

Add JOIN compatibility validation to the discovery process:

1. **Sample-based JOIN Key Detection**
   - For each pair of discovered tables, examine sample values
   - Identify potential JOIN keys based on:
     - Column name similarity (e.g., `user_id`, `userId`, `USER_ID`)
     - Data type compatibility
     - Value overlap in samples (e.g., do sample values from one column appear in another?)
   
2. **JOIN Graph Construction**
   - Build a graph of tables where edges represent viable JOIN paths
   - Ensure all returned tables form a connected component
   - Or explicitly document which tables can be joined and which cannot

3. **Metadata Enhancement**
   - Add `join_hints` to discovered datasets:
     ```json
     {
       "table_id": "transactions",
       "potential_joins": [
         {
           "target_table": "users",
           "local_key": "user_id",
           "foreign_key": "id",
           "confidence": 0.9,
           "sample_overlap": 0.85
         }
       ]
     }
     ```
   
4. **Discovery Filtering**
   - Optionally filter out tables that cannot be joined to the main dataset cluster
   - Or rank tables by their JOIN-ability

### Implementation Considerations

- **Performance**: JOIN validation adds overhead to discovery
  - Could be made optional via parameter
  - Could be cached if same tables are discovered frequently
  
- **False Positives/Negatives**: 
  - Sample-based detection may miss valid JOINs (false negative)
  - May suggest invalid JOINs based on coincidental value overlap (false positive)
  - Should provide confidence scores, not binary yes/no
  
- **Multi-table JOINs**:
  - Complex insights may require 3+ table JOINs
  - Need to handle transitive relationships (A joins to B, B joins to C)

### Expected Benefits

1. **Fewer Failed Queries**: Query generation starts with tables that can actually be joined
2. **Reduced LLM Costs**: Fewer refinement iterations needed
3. **Faster Query Generation**: Less time spent on doomed approaches
4. **Better User Experience**: More likely to get working queries on first attempt

### Related Improvements

This complements the query-generation-agent improvements:
- Generation prompt now emphasizes using sample values to verify JOINs will work
- Refinement prompt includes full history to avoid repeating failed JOIN strategies
- NULL-heavy result detection catches attempts to "game" validation with empty results

### Priority

**Medium-High**: While the query-generation improvements help the agent adapt to incompatible tables, preventing the issue at discovery time would be more efficient.

### Estimated Effort

- **Small**: Add basic column name matching for potential JOINs (1-2 days)
- **Medium**: Add sample value overlap analysis (3-5 days)
- **Large**: Build full JOIN graph with filtering (1-2 weeks)

