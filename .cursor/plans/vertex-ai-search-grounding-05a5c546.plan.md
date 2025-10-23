<!-- 05a5c546-fa51-4abc-aee7-3dab3a1ae68a 7897a47b-1fa7-4eb9-ae92-312b1b226923 -->
# Refactor Prompts to Focus on Data Product Definition (Not Tactical Inputs)

## Problem

The current prompts conflate two distinct activities:

1. **Building a data product** (the PRP's job) - defining WHAT to build
2. **Using a data product** (execution) - providing specific INPUT VALUES

### Example of the Issue

**Current behavior**: When user says "should we enter the European market?", the system asks:

- ❌ "Which country are you considering?" (tactical input for this specific decision)
- ❌ "What is your current revenue?" (specific instance data)

**Desired behavior**: System should ask:

- ✅ "What type of analysis: one-time market entry decision vs. reusable market opportunity evaluator?"
- ✅ "What metrics define market attractiveness: revenue potential, competition level, cost to serve?"
- ✅ "What makes a 'good' market: immediate revenue, long-term growth, or strategic positioning?"

## Core Distinction

| Data Product Definition (PRP) | Data Product Usage (Execution) |

|-------------------------------|-------------------------------|

| What type of analysis? | Which specific products/customers? |

| What metrics matter? | What are my current sales numbers? |

| What defines success? | Should we launch Product A or B? |

| Who is the audience? | Run this analysis for me now |

| How often is this used? | Give me today's results |

**The PRP should define the LEFT column, not gather the RIGHT column.**

## Solution Overview

### Phase 1: Add Data Product Type Classification

Add explicit prompt to classify what type of data product they want:

**Types**:

- **Reusable Tool/Dashboard**: Used regularly (e.g., "Weekly customer churn analysis by segment")
- **One-Time Analysis**: Answers a specific question once (e.g., "Should we launch this product in Q4?")
- **Decision Framework**: Repeatable decision process (e.g., "New market entry evaluator I can use for all opportunities")
- **Monitoring/Alert**: Ongoing tracking (e.g., "Alert me when key revenue metrics deviate from forecast")

This clarifies scope and helps avoid asking for instance-specific inputs.

### Phase 2: Refactor Initial Questions Prompt

Update prompts to ask about **data product structure**, not tactical inputs.

### Phase 3: Refactor Follow-up Questions Prompt

Ensure follow-ups continue focusing on product definition, not execution inputs.

### Phase 4: Update Data PRP Generation

Ensure final PRP clearly separates:

- **Product Requirements**: What the tool does, what metrics it uses, how it's structured
- **Example Usage**: How someone would use this tool with specific inputs

## Detailed Changes

### 1. Add Product Type Classification to Initial Questions

**File**: `src/data_planning_agent/clients/gemini_client.py` - `generate_initial_questions()`

After line 305, before building prompts, add a classification step:

```python
# First, classify what type of data product they want
product_type_prompt = f"""Based on this user intent:

"{initial_intent}"

What type of data product are they asking for?

A) ONE-TIME ANALYSIS: They want to answer one specific question right now
   Example: "Should we launch Product X in the Q4 holiday season?"
   
B) REUSABLE TOOL: They want a tool they can use repeatedly with different inputs
   Example: "A product profitability comparison tool for evaluating new SKUs"
   
C) DECISION FRAMEWORK: They want a systematic approach to a recurring decision
   Example: "A customer segment prioritization framework for marketing campaigns"
   
D) MONITORING/DASHBOARD: They want ongoing tracking and updates
   Example: "Track weekly revenue trends by product category and region"

Respond with ONLY the letter (A, B, C, or D):"""

# Get classification
type_response = self.model.generate_content(product_type_prompt, ...)
product_type = type_response.text.strip().upper()[0]  # Get A, B, C, or D
```

### 2. Update Initial Questions Prompts Based on Product Type

Modify the prompt templates to include product type guidance:

```python
if context_type == "exact_match":
    if product_type == 'A':  # One-time analysis
        guidance = """This appears to be a ONE-TIME ANALYSIS request. Help them define:
- What specific question they're trying to answer
- What metrics/data would answer it
- What timeframe is relevant
- What would constitute a clear answer

DO NOT ask for specific input values like product names, customer IDs, dates, or entity identifiers."""
    
    elif product_type in ['B', 'C']:  # Reusable tool/framework
        guidance = """This appears to be a REUSABLE TOOL/FRAMEWORK request. Help them define:
- What type of comparisons or decisions this tool supports
- What metrics are most important for the comparison
- What parameters users would provide when using the tool
- What makes a "good" vs "bad" outcome
- How often this would be used

DO NOT ask for specific instance inputs - focus on the STRUCTURE of the tool."""
    
    elif product_type == 'D':  # Monitoring
        guidance = """This appears to be a MONITORING/DASHBOARD request. Help them define:
- What metrics to track over time
- What changes or thresholds trigger interest
- How often to update (daily, weekly, real-time)
- What alerts or notifications are needed

DO NOT ask for specific current values - focus on what to MONITOR."""
    
    else:
        guidance = ""

    prompt = f"""You are an expert data analyst helping define a DATA PRODUCT.

User's intent: {preprocessed_intent}

{guidance}

AVAILABLE DATA (exact match):
{datastore_context}

Ask up to 3 questions to define the DATA PRODUCT STRUCTURE (not to gather specific inputs).

FOCUS ON:
- What type of analysis framework to build
- What metrics and dimensions are needed
- What defines success or a good outcome
- How this would be used (once vs. repeatedly)

DO NOT ASK FOR:
- Specific product names, customer IDs, or entity identifiers
- Current business metrics or account details
- Specific dates or time periods for this run
- Any values that would be "inputs" to the tool rather than part of its definition

IMPORTANT: Prefer multiple choice questions (a, b, c, d format).

Generate your questions now:"""
```

### 3. Update Follow-up Questions Prompt

**File**: `src/data_planning_agent/clients/gemini_client.py` - `generate_follow_up_questions()`

Update the prompt at line 495:

```python
prompt = f"""You are an expert data analyst defining a DATA PRODUCT (not answering a one-time question).

Conversation so far:
{conversation_text}
{context_section}

Your task: Determine if you have enough information to define the DATA PRODUCT STRUCTURE.

REMEMBER: You're defining WHAT TO BUILD, not gathering inputs to run it.

A complete Data Product definition requires:
1. **Product Type**: One-time analysis, reusable tool, decision framework, or dashboard
2. **Objective**: What business question or decision this supports
3. **Key Metrics**: What measurements matter (not specific values, but which metrics to include)
4. **Dimensions**: What breakdowns or comparisons (not specific entities, but what types)
5. **Success Criteria**: What makes a good/useful output
6. **Frequency**: One-time or recurring? If recurring, how often?

AVOID asking for:
- Specific entity identifiers (product names, customer IDs, user IDs)
- Current state or starting values
- Specific time windows for "this run"
- Any inputs that would be provided when USING the tool

GOOD QUESTIONS (product structure):
- "What metrics best measure success for this comparison?"
- "Should this be a one-time analysis or a reusable weekly tool?"
- "What makes a 'good' vs 'bad' outcome in your evaluation?"

BAD QUESTIONS (tactical inputs):
- "What is your current market share?" ❌
- "What date range do you want to analyze?" ❌  
- "Which specific customer segment are you targeting?" ❌

Based on available data and the conversation so far:
- Understand if we have data to build this product
- Guide them toward feasible product designs
- Suggest alternative approaches if exact data doesn't exist

If you have SUFFICIENT information to define the data product structure, respond: "COMPLETE"

If you MUST ask more questions (only for fundamental product definition gaps), ask up to 3:
- STRONGLY prefer multiple choice
- Focus on PRODUCT STRUCTURE, not execution inputs
- Use available data to ask informed questions

Provide your response now:"""
```

### 4. Update Data PRP Generation Template

**File**: `src/data_planning_agent/clients/gemini_client.py` - `generate_data_prp()`

Update the PRP generation prompt to clearly separate product definition from usage:

```python
prompt = f"""Generate a Data Product Requirement Prompt (Data PRP) from this conversation.

Conversation:
{conversation_text}
{context_section}

CRITICAL: This PRP defines a DATA PRODUCT, not a one-time query result.

Structure your Data PRP with these sections:

# Data Product Requirement Prompt

## 1. Product Type
Is this a one-time analysis, reusable tool, decision framework, or dashboard?

## 2. Business Objective
What business need or decision does this support? (Not the specific instance, but the general need)

## 3. Product Functionality
What does this data product DO? Describe its capabilities.

## 4. Key Metrics
What measurements/calculations are needed? (Define the metrics, not specific values)

## 5. Dimensions & Breakdowns  
What categories, segments, or comparisons? (Define the structure, not specific entities)

## 6. Success Criteria
What makes this product useful? What defines a "good" output?

## 7. Usage Pattern
- **Frequency**: One-time, daily, weekly, on-demand?
- **Audience**: Who uses this?
- **Triggers**: What prompts someone to use it?

## 8. Example Usage Scenario
Show how someone would USE this product:
- What inputs they provide
- What outputs they get
- How they make decisions with it

## 9. Data Requirements
Based on available data:
{datastore_context if datastore_context else "- No specific data catalog information available"}

- What data sources are needed?
- What gaps exist (if any)?
- What assumptions are made?

---

IMPORTANT DISTINCTIONS:
- **Product Definition**: "Compare any two products using revenue, growth rate, and market penetration"
- **NOT Instance Execution**: "Compare Product A to Product B for Q3 results"

- **Product Definition**: "Metrics include: revenue, growth rate, customer acquisition cost, market share"
- **NOT Instance Values**: "Product A has $2.8M revenue and 15% growth"

Generate the complete Data PRP now:"""
```

### 5. Add Helper Method for Product Type Detection

**File**: `src/data_planning_agent/clients/gemini_client.py`

Add a new method before `generate_initial_questions`:

```python
def _classify_product_type(self, intent: str) -> str:
    """
    Classify what type of data product the user is requesting.
    
    Args:
        intent: User's initial intent
        
    Returns:
        Product type code: 'A' (one-time), 'B' (reusable), 'C' (framework), 'D' (monitoring)
    """
    prompt = f"""Based on this user intent:

"{intent}"

What type of data product are they asking for?

A) ONE-TIME ANALYSIS: Answer one specific question right now
B) REUSABLE TOOL: A tool to use repeatedly with different inputs  
C) DECISION FRAMEWORK: Systematic approach to recurring decisions
D) MONITORING: Ongoing tracking and updates

Respond with ONLY the letter (A, B, C, or D):"""
    
    try:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.1),
            safety_settings=self.safety_settings,
        )
        
        if response.candidates and response.candidates[0].content.parts:
            result = response.text.strip().upper()
            # Extract first letter
            for char in result:
                if char in ['A', 'B', 'C', 'D']:
                    logger.info(f"Classified product type: {char}")
                    return char
        
        # Default to one-time if unclear
        logger.warning("Could not classify product type, defaulting to 'A' (one-time)")
        return 'A'
        
    except Exception as e:
        logger.error(f"Error classifying product type: {e}")
        return 'A'  # Default to one-time
```

## Expected Changes in Behavior

### Before (Asking for Tactical Inputs)

```
User: "should we enter the European market?"

Questions:
1. Which country are you targeting? ❌
2. What is your current annual revenue?
3. What is your company size?
```

### After (Asking for Product Structure)

```
User: "should we enter the European market?"

Questions:
1. What type of analysis would be most valuable?
   a) One-time market entry decision for this specific opportunity
   b) Reusable market opportunity evaluator for all regions
   c) Ongoing market performance dashboard for multiple markets
   
2. What metrics best determine market attractiveness?
   a) Total addressable market size
   b) Competitive intensity and market share potential
   c) Projected revenue and profitability
   d) Strategic alignment and growth trajectory
   
3. What defines a "good" market for your business?
   a) Immediate revenue opportunity in next 1-2 quarters
   b) Strong long-term growth potential
   c) Strategic positioning for future expansion
```

## Benefits

✅ **Clearer scope**: User understands they're defining a product, not getting an answer

✅ **Reusability**: PRP defines something that can be built and reused

✅ **Better requirements**: Focus on structure, not instance data

✅ **Avoids confusion**: Separates "what to build" from "how to use it"

✅ **More valuable**: Reusable tools > one-time answers

## Files to Modify

1. `src/data_planning_agent/clients/gemini_client.py`

   - Add `_classify_product_type()` method
   - Update `generate_initial_questions()` prompts
   - Update `generate_follow_up_questions()` prompt
   - Update `generate_data_prp()` prompt structure

## Testing Scenarios

1. **One-time question** ("should we launch product X?") → Clarify if they want one answer or a reusable tool
2. **Reusable tool** ("product profitability analyzer") → Ask about metrics, not specific products
3. **Decision framework** ("market entry evaluator") → Ask about decision criteria, not current markets
4. **Monitoring** ("track revenue performance") → Ask about what to monitor, not current values

### To-dos

- [ ] Create SearchFanoutGenerator class that uses Gemini to generate related search queries
- [ ] Add search_with_fanout method to VertexSearchClient
- [ ] Add format_fanout_results method to VertexSearchClient to handle exact/related/no match scenarios
- [ ] Update GeminiClient._query_datastore to use fan-out strategy and return context type
- [ ] Update generate_initial_questions to adapt prompts based on context type (exact/related/no match)
- [ ] Update generate_follow_up_questions to use fan-out context types
- [ ] Update generate_data_prp to use fan-out context types
- [ ] Add ENABLE_SEARCH_FANOUT and SEARCH_FANOUT_COUNT to config
- [ ] Add fan-out configuration to .env.example