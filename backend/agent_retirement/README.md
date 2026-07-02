# Agent Retirement

Bedrock AgentCore implementation of the retirement specialist agent that provides comprehensive retirement planning analysis and projections.

## Overview

This agent analyzes portfolio data and user retirement goals to provide detailed retirement readiness assessments, Monte Carlo simulation results, and actionable recommendations for retirement planning.

## Features

- **Retirement Readiness Analysis**: Comprehensive assessment of current retirement preparedness
- **Monte Carlo Simulations**: 500-scenario probabilistic analysis for retirement success
- **Asset Allocation Analysis**: Evaluation of portfolio allocation appropriateness for retirement timeline
- **Risk Assessment**: Analysis of sequence of returns, inflation, and longevity risks
- **Actionable Recommendations**: Specific, timeline-based advice to improve retirement outcomes
- **Database Integration**: Automatic saving of retirement analysis

## Architecture

Built using:
- **Strands**: Core agent framework
- **Bedrock AgentCore**: AWS Bedrock integration
- **BedrockModel**: Direct AWS Bedrock model access
- **Monte Carlo Engine**: Statistical retirement projections
- **Aurora Database**: Analysis storage and user data

## Dependencies

- `strands>=0.8.4`: Core agent framework
- `bedrock-agentcore>=1.0.0`: AWS Bedrock integration
- `alex-database`: Shared database library
- `boto3`: AWS SDK
- `pydantic`: Data validation
- `python-dotenv`: Environment configuration

## Environment Variables

Required environment variables:

```bash
BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
BEDROCK_REGION=us-west-2
```

## Usage

### As BedrockAgentCore App

```python
from agent import app

# Run as Bedrock AgentCore app
if __name__ == "__main__":
    app.run()
```

### Direct Function Call

```python
from agent import process_retirement_analysis

payload = {
    "job_id": "unique-job-id",
    "portfolio_data": {
        "accounts": [
            {
                "name": "401(k)",
                "type": "retirement",
                "cash_balance": 10000,
                "positions": [
                    {
                        "symbol": "SPY",
                        "quantity": 100,
                        "instrument": {
                            "name": "SPDR S&P 500 ETF",
                            "current_price": 450,
                            "allocation_asset_class": {"equity": 100.0}
                        }
                    }
                ]
            }
        ]
    }
}

result = await process_retirement_analysis(
    payload["job_id"],
    payload["portfolio_data"]
)
```

## Testing

### Simple Test (with real database)

```bash
uv run test_simple.py
```

### Full Test (with Bedrock)

```bash
uv run test_full.py
```

## Analysis Components

### Monte Carlo Simulation

Runs 500 scenarios analyzing:
- **Accumulation Phase**: Portfolio growth until retirement
- **Distribution Phase**: 30-year retirement income sustainability
- **Risk Factors**: Market volatility, sequence of returns, inflation
- **Success Metrics**: Probability of maintaining target income

### Key Metrics

1. **Success Rate**: Percentage of scenarios sustaining 30-year retirement
2. **Expected Value at Retirement**: Mean portfolio value at retirement age
3. **Percentile Analysis**: 10th, 50th, and 90th percentile outcomes
4. **Years Portfolio Lasts**: Average duration of income sustainability

### Risk Analysis

- **Sequence of Returns Risk**: Poor early retirement returns impact
- **Inflation Impact**: 3% annual inflation adjustment
- **Longevity Risk**: Planning beyond 30-year retirement
- **Market Volatility**: Asset class return variability

## Output Format

Generated analysis includes:

1. **Retirement Readiness Assessment**: Clear probability-based evaluation
2. **Monte Carlo Results**: Success rates and outcome distributions
3. **Asset Allocation Review**: Appropriateness for retirement timeline
4. **Risk Mitigation Strategies**: Specific recommendations for risk reduction
5. **Action Items**: Timeline-based recommendations for improvement
6. **Gap Analysis**: Difference between current trajectory and goals

## Mathematical Models

### Expected Returns
- **Equity**: 7% mean, 18% standard deviation
- **Bonds**: 4% mean, 5% standard deviation
- **Real Estate**: 6% mean, 12% standard deviation
- **Cash**: 2% fixed return

### Assumptions
- **Annual Contributions**: $10,000 during accumulation
- **Withdrawal Rate**: 4% rule for retirement income
- **Inflation**: 3% annual adjustment
- **Retirement Duration**: 30 years

## Error Handling

- Comprehensive error handling and logging
- Database transaction safety
- Default values for missing user preferences
- Graceful handling of calculation edge cases

## Integration

This agent integrates with:

- **Planner Agent**: Receives orchestration requests
- **Database**: Loads user preferences and saves analysis
- **User Management**: Clerk user ID integration
- **Aurora**: Analysis storage and retrieval

## Deployment

Deploy as part of the Alex agent orchestra using the terraform configuration in `terraform/6_agents/`.