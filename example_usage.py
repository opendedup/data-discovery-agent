"""Example usage of the data profiler agent."""

import os
from dotenv import load_dotenv
from data_discovery_agent.agents.data_profiler.agent import root_agent

# Load environment variables from .env file
load_dotenv()

# Ensure GOOGLE_API_KEY is set
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError(
        "GOOGLE_API_KEY not found in environment. "
        "Please set it in your .env file or environment variables."
    )


def main():
    """Run the data profiler agent with an example query."""
    
    # Example usage - you can pass actual data here
    example_data = """
    Here's a sample dataset in CSV format:
    
    Name,Age,Salary,Department
    Alice,28,75000,Engineering
    Bob,35,85000,Engineering
    Charlie,42,95000,Management
    Diana,31,72000,Marketing
    Eve,29,68000,Marketing
    Frank,45,120000,Executive
    """
    
    query = f"Please profile this dataset and provide insights:\n{example_data}"
    
    print("Starting data profiler agent...")
    print("-" * 50)
    
    # Generate response from the agent
    response = root_agent.generate(query)
    
    print("Agent Response:")
    print(response.text)
    print("-" * 50)


if __name__ == "__main__":
    main()

