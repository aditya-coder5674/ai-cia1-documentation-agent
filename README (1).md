# Documentation Agent: a Learning Agent for Software Documentation

**CIA-1 Part 5 | AI (ITPCC510) | Semester V | Academic Year 2026-27**

## Student Details
| | |
|---|---|
| Name | Aditya Kottari |
| Roll No. | 5024132 |
| Class | Third Year, Information Technology (Sem V) |
| Institute | Fr. C. Rodrigues Institute of Technology, Vashi |
| Course | ITPCC510 - Artificial Intelligence |
| Faculty | Dr. S. L. Vaikole |

## Overview
Writing software documentation (requirements, test cases) is slow and repetitive. This project is a small **learning agent** that uses an LLM to generate SRS requirements and test cases for a software project, **checks its own output**, and **improves it** from v1 to v2, the same iterative process described in the referenced IEEE paper.

Example project used for the demo: a *Professional Networking App* (the same kind of project the paper used).

## Application Screenshot
![Application screenshot](screenshots/run.png)

## Tech Stack
- **Language:** Python 3.9+ (standard library only, no installs)
- **AI tool:** Google Gemini API (LLM) through its REST endpoint
- **Output format:** Markdown files (`srs_v1.md`, `srs_v2.md`)
- **Offline mode:** a simulated LLM (`--offline`) for testing only

## Architecture
The agent follows the **learning agent** structure (Russell & Norvig):

```
   Project idea + features
            |
            v
 +-----------------------+   draft    +----------------------+
 | Performance element   | ---------> | Critic               |
 | LLM writes            |            | Checks coverage:     |
 | requirements + tests  |            | every feature has a  |
 +-----------------------+            | requirement; every   |
            ^                         | requirement has a    |
            |                         | positive + negative  |
            |     lessons             | test                 |
 +-----------------------+  issues    +----------------------+
 | Learning element      | <----------------------+
 | Stores critic         |
 | feedback as lessons   |
 | in the next prompt    |
 +-----------------------+
```

| Component | Where in code | What it does |
|---|---|---|
| Performance element | `generate()` | LLM generates requirements and test cases |
| Critic | `critic()` | Rule-based coverage checker (no LLM) |
| Learning element | `learn()` | Converts issues into lessons for the next version |

**PEAS:** Performance = coverage and documentation quality, time saved. Environment = software project documentation. Actuators = writes requirements, test cases, and files. Sensors = project idea, features, critic feedback.

## Working
1. Provide the project name, idea and feature list.
2. The LLM generates **v1** (requirements plus positive/negative test cases).
3. The critic scores coverage and lists problems (for example, "REQ-02 has no negative test case").
4. The learning element stores these problems as lessons.
5. The lessons and the previous draft are added to the prompt, and the LLM generates **v2**.
6. The loop repeats (maximum 3 rounds) until the critic finds no issues.
7. Each version is saved as a Markdown file and a summary table is printed.

**Note on "learning":** no model weights are changed. The agent improves through feedback stored in the prompt (iterative prompting), which matches the method in the paper.

## Sample Output
> The output below is from the `--offline` simulated-LLM run. A live Gemini run gives similar structure with real text.

```
--- Version 1 ---  saved output/srs_v1.md
requirements=8  tests=12  coverage=50%
  critic: Feature 'Job posting and applying' has no requirement - add requirements for it.
  critic: REQ-02 has no negative test case - add one.
  ...
  learning element stored 5 lesson(s) for the next version

--- Version 2 ---  saved output/srs_v2.md
requirements=10  tests=20  coverage=100%
  critic: no issues, agent stops.

Version | Reqs | Tests | Coverage
   v1   |    8 |    12 |     50%
   v2   |   10 |    20 |    100%
```
Full generated documents: [`sample_output/srs_v1.md`](sample_output/srs_v1.md) and [`sample_output/srs_v2.md`](sample_output/srs_v2.md).

## How to Run
```bash
# 1. Get a free API key from https://aistudio.google.com
export GEMINI_API_KEY=your_key        # Windows: set GEMINI_API_KEY=your_key

# 2. Run
python doc_agent.py

# Optional: simulated LLM, no key needed
python doc_agent.py --offline
```
If a model name error appears, set `GEMINI_MODEL` to another available Gemini model.

## Demo Walkthrough
1. Show the problem: writing requirements and tests by hand is slow.
2. Run `python doc_agent.py`.
3. Point out **v1**: the critic finds gaps (missing tests or features), so coverage is below 100%.
4. Point out the **learning element** storing lessons.
5. Point out **v2**: the gaps are fixed and coverage reaches 100%.
6. Open `output/srs_v1.md` and `output/srs_v2.md` side by side to show the improvement.
7. Explain how this connects to Part 1 (learning agent), Part 4 (feedback-based improvement) and the paper.

## Limitations
- The critic checks **structure and coverage**, not whether the requirements are truly correct. A human must still review them.
- Manual-effort comparisons in the code are assumptions, not measurements.
- The paper found that project plans still need human guidance, so this project covers only the SRS and test cases.

## Reference
R. Gadamsetty, K. A. Demir and B. Liu, "Generative AI for Software Engineering: Generative AI Effectiveness and Efficiency in Software Development Documentation," *2025 Conference on AI x Software Engineering (AIxSE)*, IEEE, 2025, pp. 76-80. DOI: 10.1109/AIxSE64906.2025.00017
