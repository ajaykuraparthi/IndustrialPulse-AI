# AI Contribution Statement

## 1. AI Tools Used

### ChatGPT
ChatGPT was used as a development assistant to help plan implementation tasks, formulate coding instructions, review test results, identify potential issues, and prepare documentation.

### OpenAI Codex
Codex was used to generate substantial parts of the project from my instructions and to implement, debug, review, and improve existing features. I used it to help develop and refine the dashboard, inspect API behavior, improve error handling, and review repository readiness.

No other AI tools were used for this project.

## 2. Human Review and Validation

I reviewed the implementation and development reports, checked changes to the repository, and used the available verification results to assess whether the application behaved as expected.

The reported validation included:
- 12 passing automated tests.
- Scenario evaluation with two exact matches and two facility-level proxy outcomes.
- A reproducibility check using 1,000 generated telemetry records.
- API workflow checks using temporary data and an isolated SQLite database.
- Browser checks covering dashboard rendering, error handling, and simulation interactions.

These checks have different scopes. They do not establish that the application is production-ready or that its detection rules have been validated on real industrial data.

## 3. Technical Limitations

IndustrialPulse AI uses synthetic telemetry and illustrative thresholds. Its pump calculation is a simplified affinity-law estimate, not a hydraulic network solution. Leak and blockage scenarios may produce facility-level proxy outcomes rather than exact component-level detections.

The application is an educational prototype and has not been validated for safety-critical industrial monitoring.

## 4. Prompt History

The accompanying `prompt_history.md` records prompts submitted to ChatGPT and OpenAI Codex.

Original prompts should be preserved wherever available. Any reconstructed prompts must be explicitly identified as reconstructed. The history should cover the full development process, not only the final review.