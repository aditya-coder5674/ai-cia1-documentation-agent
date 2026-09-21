"""
Documentation Agent  --  CIA-1 Part 5 (AI, ITPCC510)

A small LEARNING AGENT that generates SRS requirements + test cases for a
software project using an LLM, checks its own work, and improves (v1 -> v2 -> ...)
exactly like the two-version process in the IEEE paper.

Learning-agent parts (Russell & Norvig) and where they are in this file:
    Performance element : generate()  -> LLM writes requirements + test cases
    Critic              : critic()    -> checks coverage (rule-based, no LLM)
    Learning element    : learn()     -> turns critic feedback into "lessons"
    Problem generator   : (optional, not implemented)

Run:
    python doc_agent.py              # real LLM (needs GEMINI_API_KEY)
    python doc_agent.py --offline    # simulated LLM, for testing / backup only
"""
import json
import os
import sys
import time
import urllib.request

# ---------------------------------------------------------------- the problem
PROJECT = {
    "name": "Professional Networking App",
    "idea": "A web app where professionals build profiles, connect, "
            "share posts, message each other and apply for jobs.",
    "features": [
        "User registration and profile",
        "Connect with other users",
        "News feed with posts",
        "Messaging",
        "Job posting and applying",
    ],
}
MAX_ROUNDS = 3
MANUAL_MINUTES = 120   # ASSUMPTION: typical manual effort for this small SRS+tests
OUT_DIR = "output"


# ------------------------------------------------------ performance element
def build_prompt(project, lessons, previous):
    head = (
        f"You are a software documentation assistant.\n"
        f"Project: {project['name']} - {project['idea']}\n"
        f"Features: {json.dumps(project['features'])}\n\n"
    )
    shape = (
        "Set each requirement's 'feature' to EXACTLY one of the feature strings above. "
        "'type' is 'positive' (success case) or 'negative' (failure case).\n"
        "Return ONLY JSON in this shape:\n"
        '{"requirements":[{"id":"REQ-01","feature":"...","text":"..."}],'
        '"test_cases":[{"id":"TC-01","requirement_id":"REQ-01",'
        '"type":"positive","description":"..."}]}\n'
    )
    if not previous:
        # Version 1 = a quick first draft (like a first, un-refined prompt in the paper)
        return (head + "Write a QUICK FIRST DRAFT of the SRS: exactly 1 functional "
                "requirement per feature and exactly 1 test case per requirement.\n" + shape)
    # Later versions = improve the previous draft using the learned lessons
    return (head + "Improve your previous draft. Keep everything that is already good, "
            "and fix EVERY lesson below by adding what is missing.\n" + shape +
            "\nYour previous draft:\n" + json.dumps(previous) +
            "\n\nLESSONS from reviewing earlier drafts:\n" +
            "\n".join(f"- {x}" for x in lessons) + "\n")


def call_gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY first (or run with --offline).")
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    data = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 5:
                wait = 5 * attempt
                print(f"  Gemini is busy (error {e.code}), retrying in {wait}s "
                      f"(attempt {attempt}/5)...")
                time.sleep(wait)
                continue
            sys.exit(f"Gemini API error {e.code} for model '{model}': "
                     f"{e.read().decode(errors='ignore')[:300]}\n"
                     "Tip: try again in a minute, or set GEMINI_MODEL to another "
                     "model name from aistudio.google.com")
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text.strip().removeprefix("```json").removesuffix("```"))


def mock_llm(project, round_no):
    """Simulated LLM (backup only). Round 1 is deliberately incomplete."""
    feats = project["features"]
    use = feats if round_no > 1 else feats[:-1]      # v1 forgets the last feature
    reqs, tcs = [], []
    for f in use:
        for k in (1, 2):
            rid = f"REQ-{len(reqs) + 1:02d}"
            reqs.append({"id": rid, "feature": f, "text": f"The system shall support {f.lower()} (part {k})."})
    for i, r in enumerate(reqs):
        tcs.append({"id": f"TC-{len(tcs)+1:02d}", "requirement_id": r["id"], "type": "positive",
                    "description": f"Valid input for {r['id']} succeeds."})
        if round_no > 1 or i % 2 == 0:               # v1 misses half the negative tests
            tcs.append({"id": f"TC-{len(tcs)+1:02d}", "requirement_id": r["id"], "type": "negative",
                        "description": f"Invalid input for {r['id']} is rejected."})
    return {"requirements": reqs, "test_cases": tcs}


def generate(project, lessons, previous, round_no, offline):
    if offline:
        return mock_llm(project, round_no)
    return call_gemini(build_prompt(project, lessons, previous))


# ------------------------------------------------------------------- critic
def critic(project, doc):
    """Rule-based checker. Returns (score %, list of issues)."""
    issues = []
    reqs = doc["requirements"]
    for f in project["features"]:
        if not any(r.get("feature", "").lower() == f.lower() for r in reqs):
            issues.append(f"Feature '{f}' has no requirement - add requirements for it.")
    good = 0
    for r in reqs:
        types = {t["type"] for t in doc["test_cases"] if t["requirement_id"] == r["id"]}
        missing = [x for x in ("positive", "negative") if x not in types]
        for m in missing:
            issues.append(f"{r['id']} has no {m} test case - add one.")
        good += not missing
    score = 100 * good / len(reqs) if reqs else 0
    return score, issues


# ---------------------------------------------------------- learning element
def learn(lessons, issues):
    """Feedback from the critic becomes lessons remembered for the next round."""
    for i in issues:
        if i not in lessons:
            lessons.append(i)
    return lessons


# ------------------------------------------------------------------- output
def save_markdown(doc, version, score):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"srs_v{version}.md")
    with open(path, "w") as f:
        f.write(f"# SRS v{version} - {PROJECT['name']}  (coverage {score:.0f}%)\n\n")
        f.write("## Requirements\n| ID | Feature | Requirement |\n|---|---|---|\n")
        for r in doc["requirements"]:
            f.write(f"| {r['id']} | {r['feature']} | {r['text']} |\n")
        f.write("\n## Test cases\n| ID | Requirement | Type | Description |\n|---|---|---|---|\n")
        for t in doc["test_cases"]:
            f.write(f"| {t['id']} | {t['requirement_id']} | {t['type']} | {t['description']} |\n")
    return path


def main():
    offline = "--offline" in sys.argv
    print(f"=== Documentation Agent | {'OFFLINE (simulated LLM)' if offline else 'live LLM'} ===")
    print(f"Project: {PROJECT['name']}\n")
    lessons, previous, history = [], None, []
    total_sec = 0.0

    for n in range(1, MAX_ROUNDS + 1):
        t0 = time.time()
        doc = generate(PROJECT, lessons, previous, n, offline)     # performance element
        sec = time.time() - t0
        total_sec += sec
        score, issues = critic(PROJECT, doc)                       # critic
        path = save_markdown(doc, n, score)
        history.append((n, len(doc["requirements"]), len(doc["test_cases"]), score, sec))
        print(f"--- Version {n} ---  saved {path}")
        print(f"requirements={len(doc['requirements'])}  tests={len(doc['test_cases'])}  "
              f"coverage={score:.0f}%  time={sec:.1f}s")
        for i in issues[:5]:
            print("  critic:", i)
        if len(issues) > 5:
            print(f"  ...and {len(issues) - 5} more issues")
        if not issues:
            print("  critic: no issues, agent stops.\n")
            break
        lessons = learn(lessons, issues)                           # learning element
        previous = doc
        print(f"  learning element stored {len(lessons)} lesson(s) for the next version\n")

    print("=== Summary ===")
    print("Version | Reqs | Tests | Coverage | Time")
    for n, r, t, s, sec in history:
        print(f"   v{n}   | {r:4d} | {t:5d} | {s:6.0f}%  | {sec:.1f}s")
    mins = total_sec / 60
    print(f"\nAgent total: {mins:.2f} min  vs  assumed manual effort: {MANUAL_MINUTES} min "
          f"(manual figure is an assumption, not measured)")


if __name__ == "__main__":
    main()
