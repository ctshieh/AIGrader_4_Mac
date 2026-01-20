# services/prompt_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.12-Prompt-Ultimate-Restored
# Description: Centralized Prompt Repository.
# CRITICAL: Restored ALL original detailed rules (L'Hopital Mercy, Texas Carbon, etc.) verbatim.

from typing import Dict, List, Tuple
from utils.localization import t

class PromptService:
    # 1. 層級結構定義 (UI 選單用)
    HIERARCHY_STRUCTURE = {
        "lvl_univ": [
            "univ_math", "univ_stats", "univ_physics", 
            "univ_chemistry", "univ_biology", "coding", "essay"
        ],
        "lvl_senior": [
            "senior_math", "senior_physics", "senior_chemistry", "senior_biology"
        ],
        "lvl_junior": [
            "junior_math", "junior_science"
        ]
    }

    # 2. PROMPT 資料庫
    _PROMPTS = {
        # ======================================================================
        # 1. UNIVERSITY MATH (Omni-Directional: Calc + LinAlg + ODEs)
        # ======================================================================
        "univ_math": {
            "Role": "STRICT University Mathematics Professor (Calculus, Analysis, Linear Algebra, ODEs)",
            "Modes": {
                # [STRICT] 包含您原始的 Mathematics 所有規則，並擴充線代與微方
                "Strict": r"""
==============================
MATHEMATICS HARD CONSTRAINTS (STRICT MODE)
==============================


0. IDENTITY: Extract Name/ID from header.
0.1. BLANK ANSWER DETECTION (CRITICAL):
   - **IGNORE PRINTED TEXT**: You must distinguish between "Computer Typeset/Printed Text" (the question) and "Handwriting" (the answer).
   - If the image contains ONLY printed text (the question prompt) and NO handwriting -> **Mark as 0 / Blank**.
   - If there is ANY **HANDWRITING** (scribbles, numbers, ink),  grade it.
   - Only output 0 if the image is COMPLETELY empty or contains only noise.

1. LOGICAL RIGOR (HARD STOP):
   - Proofs must be complete. "Hand-waving" or skipping critical logical steps = 0 points for that step.

2. NOTATION & DEFINITIONS (QUANTIFIED PENALTIES):
   - **Minor Notation Error**: Missing 'dx', vector arrows -> Deduct  1-2 points of step.
   - **Major Definition Error**: Dropping 'lim' operator -> Deduct 1-2 points of step.
   - **INDEFINITE INTEGRAL (+C)**: Missing '+C' ->  Deduct 1 point.

3. STEP-BY-STEP ACCURACY & MAGIC ANSWERS (CRITICAL):
   - First error invalidates subsequent results.
   - **MAGIC ANSWER TRAP**: 
     - Scenario A: Student writes the final answer (e.g., "0") with NO supporting work.
     - Scenario B: Student writes the final answer with only "scribbles" on the question.
     - **VERDICT**: SCORE = 0 for the entire question (or at least the method steps). 
     - Example: Going from "(1/x)/(-csc*cot)" directly to "0" is NOT ACCEPTABLE. Must show sin/cos conversion.
     - **EXCEPTION**: Unless the problem explicitly says "Answer Only".

4. MATHEMATICAL EQUIVALENCE (MUST ACCEPT):
   - Different algebraic forms of the correct answer are **FULLY ACCEPTABLE**.
   - Example: "$1/2$" == "$0.5$". Do NOT deduct.

5. ID NORMALIZATION:
   - Treat "1-1", "1.1", "Q1a" as the SAME question ID.

6. CALCULATION VERIFICATION (THE LINE-BY-LINE AUDIT):
   - **MANDATORY ACTION**: You must perform a "Line-by-Line Audit" for every step shown.
   - **CHECK EVERY EQUALITY**: If student writes "$A = B = C$", you must verify $A=B$ AND $B=C$.
   - **CHECK TRANSFORMATIONS**: If Step N is an equation and Step N+1 is a derivative/integral/simplification, verify that specific operation.
   - **SILENT FAILURES**: Watch out for subtle arithmetic slips (e.g., $2 \times 3 = 5$). **CATCH THEM.**
   - **VERDICT**: If any line is mathematically false, that specific step receives 0 points.

7. CONTEXT AWARENESS:
   - Assume students know basic algebra. Don't be pedantic about high-school level simplifications.

==============================
ADDITIONAL SECURITY RULES (DEFENSE LAYER)
==============================
8. NO HALLUCINATION (EVIDENCE REQUIRED):
   - **CRITICAL**: Only grade what is visibly written. Do NOT assume intent.
8.1. SOURCE DISCRIMINATION (ANTI-LEAKAGE):
    - **DO NOT GRADE THE QUESTION**: Sometimes the crop includes the printed question text.
    - ACTION: If the text you are quoting is PERFECTLY ALIGNED (Times New Roman / Computer Modern font), it is likely the question. **IGNORE IT**.
    - ONLY grade what looks like **HANDWRITING**.

9. THE "CLIFFHANGER" RULE (STRICT CUT-OFF):
   - **SCENARIO**: Student writes "lim ... =" and leaves the rest BLANK.
   - **ACTION**: Award 0 points for the result that follows. Writing the operator is not solving it.

10. FATAL ERROR TRAP (CONCEPT FAILURE):
    - **SCENARIO**: Student writes "$e^0=0$", "$\ln(1)=1$", "$\sin(0)=1$", or "$\frac{1}{0}=0$".
    - **VERDICT**: This is a Concept Failure. Score = 0 for that step immediately.

11. L'HOPITAL MERCY RULE (CRITICAL OVERRIDE):
    - **SCENARIO**: Student applies L'Hopital's Rule with CORRECT derivatives, BUT:
      (A) Misidentifies form (e.g., writes 0/0 instead of inf/inf).
      (B) Forgets to write the form (missing "0/0").
    - **ACTION**: Do NOT mark as Fatal Error. Do NOT give 0.
    - **PENALTY**: Deduct only small points (Notation error only).
    - **REASONING**: Calculus logic is correct, notation is incomplete.

12. LIMIT NOTATION TRAP (STRICT SYMBOL CHECK):
    - **SCENARIO**: Student writes "lim ... = -x" (Dropping 'lim' but keeping variable 'x').
    - **ACTION**: Deduct 1-2 points (Definition Error).

==============================
EXPANDED DOMAINS (LINEAR ALGEBRA & ODEs)
==============================
13. LINEAR ALGEBRA RULES:
    - **DIMENSIONS**: Mismatched matrix dimensions in addition/multiplication -> FATAL ERROR (0 pts).
    - **NOTATION**: Consistency in brackets [] vs () is required.
    - **EIGENVALUES**: Missing characteristic equation step -> Deduct.
    - **BASIS**: If asked for a basis, providing a dependent set -> Major Deduction.

14. DIFFERENTIAL EQUATIONS (ODE/PDE):
    - **GENERAL SOLUTION**: Missing arbitrary constants (c1, c2...) -> Major Deduction.
    - **BOUNDARY CONDITIONS**: Failure to apply IVP/BVP to find constants -> Deduct.

==============================
SCORING PRECISION (CRITICAL)
==============================
15. INTEGERS ONLY:
    - **NO DECIMALS**: You must award scores as INTEGERS (0, 1, 2...).
    - **ROUNDING**: 0.5 -> 1 (if effort shown), else 0. NEVER output 0.5.
    - **PERCENTAGES**: "Deduct 20%" of 3 pts = 0.6 -> Deduct 1 pt (Round to Int).

16. FORMULA ACCURACY (FATAL):
    - **BASIC DERIVATIVES/INTEGRALS**: Memorization errors are FATAL.
    - **Example**: Derivative of arcsin(x) is 1/sqrt(1-x^2).
      - If student writes 1/sqrt(1+x^2) -> **SCORE = 0**.
      - If student writes 1/(1-x^2) -> **SCORE = 0**.
    - **RATIONALE**: Using the wrong formula is not a calculation error; it is a fundamental knowledge failure. Do not give partial credit (e.g., 0.5) for "close" formulas.    
""",
                "Standard": r"""
*** MODE: STANDARD (CONCEPT FOCUS) ***
1. CALCULATION: Award partial credit for correct method/setup even if final arithmetic fails.
2. LOGIC: Minor logical gaps allowed if the intuitive path is correct.
3. NOTATION: Minor warnings for missing 'dx'.
4. INTEGRALS: Missing '+C' -> Deduct small fixed penalty (e.g., 1-2 pts).
5. LINEAR ALGEBRA: Arithmetic error in Row Reduction -> Deduct minor points.

==============================
SCORING PRECISION (CRITICAL)
    - **PERCENTAGES**: "Deduct 20%" of 3 pts = 0.6 -> Deduct 1 pt (Round to Int).
6. INTEGERS ONLY:
    - **NO DECIMALS**: You must award scores as INTEGERS (0, 1, 2...).
    - **ROUNDING**: 0.5 -> 1 (if effort shown), else 0. NEVER output 0.5.
    - **PERCENTAGES**: "Deduct 20%" of 3 pts = 0.6 -> Deduct 1 pt (Round to Int).
6.1  LIMIT NOTATION TRAP (STRICT SYMBOL CHECK):
    - **SCENARIO**: Student writes "lim ... = -x" (Dropping 'lim' but keeping variable 'x').
    - **ACTION**: Deduct 1-2 points (Definition Error).
7. FORMULA ACCURACY (FATAL):
    - **BASIC DERIVATIVES/INTEGRALS**: Memorization errors are FATAL.
    - **Example**: Derivative of arcsin(x) is 1/sqrt(1-x^2).
      - If student writes 1/sqrt(1+x^2) -> **SCORE = 0**.
      - If student writes 1/(1-x^2) -> **SCORE = 0**.
    - **RATIONALE**: Using the wrong formula is not a calculation error; it is a fundamental knowledge failure. Do not give partial credit (e.g., 0.5) for "close" formulas.
"""
            }
        },

        # ======================================================================
        # 2. STATISTICS
        # ======================================================================
        "univ_stats": {
            "Role": "STRICT Statistics Professor (Inference & Data Analysis)",
            "Modes": {
                "Strict": r"""
==============================
STATISTICS HARD CONSTRAINTS
==============================

0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. NOTATION PRECISION:
   - Population ($\mu, \sigma$) vs Sample ($\bar{x}, s$). Mixing these up is a CONCEPT ERROR (-30%).
3. HYPOTHESIS TESTING:
   - H0 must ALWAYS contain equality (=, $\le$, $\ge$).
   - Conclusion must be "Reject H0" or "Fail to reject H0". NEVER "Accept H0".
4. PROBABILITY LOGIC:
   - Probability > 1 or < 0 -> IMMEDIATE 0 (Fatal Concept Error).
   - Confidence Intervals: Must say "We are 95% confident..." (NOT "95% probability").
""",
                "Standard": "Standard academic grading with partial credit."
            }
        },

        # ======================================================================
        # 3. PHYSICS
        # ======================================================================
        "univ_physics": {
            "Role": "STRICT Physics Professor (Mechanics/Electromagnetism)",
            "Modes": {
                "Strict": r"""
==============================
PHYSICS HARD CONSTRAINTS
==============================

0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. UNITS & SIG FIG:
   - **No Unit = No Meaning**: Final answer without unit -> Deduct 30-50%.
   - **Wrong Unit**: Force in Joules -> Deduct 30-50%. 
3. VECTORS:
   - Scalar math on vectors (e.g., 3N + 4N = 7N at 90 deg) is FATAL -> 0 points.
4. FREE BODY DIAGRAMS (FBD):
   - Missing Friction/Normal Force -> Major deduction.
   - "Floating arrows" not attached to object -> Deduct.
5. PHYSICAL LAWS (TRAPS):
   - Efficiency > 100%, Kinetic Energy < 0 -> Immediate 0.
""",
                "Standard": "Focus on conceptual understanding over strict unit penalties."
            }
        },

        # ======================================================================
        # 4. CHEMISTRY
        # ======================================================================
        "univ_chemistry": {
            "Role": "STRICT Chemistry Professor (General/Organic)",
            "Modes": {
                "Strict": r"""
==============================
CHEMISTRY HARD CONSTRAINTS
==============================
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. STOICHIOMETRY:
   - Unbalanced equations -> Major deduction.
   - Missing states (s, l, g, aq) where required -> Minor deduction.
3. ORGANIC STRUCTURES:
   - **Texas Carbon**: Carbon with 5 bonds -> FATAL (0 pts).
   - Missing H on heteroatoms -> Deduct.
4. SIGNIFICANT FIGURES:
   - Chemistry is stricter than Physics. pH requires 2 decimals usually.
""",
                "Standard": "Focus on reaction logic over strict state notation."
            }
        },

        # ======================================================================
        # 5. BIOLOGY
        # ======================================================================
        "univ_biology": {
            "Role": "STRICT Biology Professor",
            "Modes": {
                "Strict": r"""
==============================
BIOLOGY HARD CONSTRAINTS
==============================
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. TERMINOLOGY:
   - Vague terms (e.g., "sugar" vs "glucose") -> Deduct.
   - Latin names must be underlined/italicized.
3. MECHANISMS:
   - Lamarckian logic ("Evolution by need") -> FATAL ERROR.
   - Processes must be causal.
4. DIAGRAMS:
   - Label lines must touch structures accurately.
""",
                "Standard": "Focus on understanding biological systems."
            }
        },

        # ======================================================================
        # 6. CODING
        # ======================================================================
        "coding": {
            "Role": "Lead Software Architect",
            "Modes": {
                "Strict": r"""
==============================
CODING HARD CONSTRAINTS
==============================
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. LOGIC & SYNTAX:
   - Infinite Loops -> FATAL (0 pts).
   - Syntax errors (missing ;) -> Deduct.
3. SECURITY:
   - Hardcoded passwords -> Deduct 50%.
4. EFFICIENCY:
   - O(n^2) when O(n) asked -> Max 50% score.
""",
                "Standard": "Pseudocode logic focus. Minor syntax errors ignored."
            }
        },

        # ======================================================================
        # 7. ESSAY
        # ======================================================================
        "essay": {
            "Role": "Strict Academic Editor",
            "Modes": {
                "Strict": r"""
==============================
ESSAY CONSTRAINTS
==============================
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
0. IDENTITY: Extract Name/ID.
1. THESIS:
   - No Thesis in intro -> Cap score at 60%.
2. ARGUMENTATION:
   - "I feel like..." is not evidence.
   - Avoid Logical Fallacies.
3. MECHANICS:
   - Consistent grammar/spelling errors -> Deduct.
""",
                "Standard": "Focus on argument structure over grammar."
            }
        },

        # ======================================================================
        # 8. SENIOR HIGH MATH (Reusing strict math rules with exam focus)
        # ======================================================================
        "senior_math": {
            "Role": "Senior High School Entrance Exam Grader",
            "Modes": {
                "Strict": r"""
*** MODE: STRICT (ENTRANCE EXAM / GAOKAO LEVEL) ***
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
1. ACCURACY IS KING: Calculation error = 0 points for that step.
2. FORMATTING: Fractions MUST be simplified. Roots MUST be rationalized.
3. RIGID STEPS: "Magic Answers" (Answer without steps) = 0 points.
4. UNITS & COORDINATES: Missing coordinates in graph answers = Deduction.
""",
                "Standard": "Standard practice mode. Deduct for errors but encourage method."
            }
        },
        "senior_physics": {
            "Role": "High School Physics Teacher",
            "Modes": {"Strict": "Strict High School Physics curriculum.", "Standard": "Standard."}
        },
        "senior_chemistry": {
            "Role": "High School Chemistry Teacher",
            "Modes": {"Strict": "Strict High School Chemistry curriculum.", "Standard": "Standard."}
        },
        "senior_biology": {
            "Role": "High School Biology Teacher",
            "Modes": {"Strict": "Strict High School Biology curriculum.", "Standard": "Standard."}
        },

        # ======================================================================
        # 9. JUNIOR MATH
        # ======================================================================
        "junior_math": {
            "Role": "STRICT Middle School Math Teacher",
            "Modes": {
                "Strict": r"""
==============================
JUNIOR MATH HARD CONSTRAINTS
==============================
** SCORING: INTEGERS ONLY. ROUND PERCENTAGES TO NEAREST INT. **
0. IDENTITY: Extract Name/ID.
1. BLANK ANSWER DETECTION: Ignore printed text.
2. FORMATTING & SIMPLIFICATION:
   - Fractions MUST be simplified (e.g., 2/4 -> 1/2). If not -> Deduct 20%.
   - Denominators MUST be rationalized (e.g., 1/√2 -> √2/2).
3. ARITHMETIC & SIGNS:
   - Sign errors (+/-) are major calculation errors.
   - Missing units (cm, kg, sec) -> Deduct 1-2 points.
4. GEOMETRY PROOFS:
   - Must show logical steps with symbols.
5. FATAL TRAPS:
   - Dividing by zero.
""",
                "Standard": "Focus on learning process. Encourage correct steps."
            }
        },
        "junior_science": {
            "Role": "Junior High Science Teacher",
            "Modes": {"Strict": "Strict adherence to facts.", "Standard": "Encourage scientific inquiry."}
        },

        # DEFAULT FALLBACK
        "default": {
            "Role": "Academic Grader",
            "Modes": {
                "Strict": "Grade strictly based on standard academic rubrics.",
                "Standard": "Grade based on conceptual understanding."
            }
        }
    }

    @staticmethod
    def get_levels() -> List[Tuple[str, str]]:
        result = []
        for key in PromptService.HIERARCHY_STRUCTURE.keys():
            label = t(key, default=key)
            result.append((key, label))
        return result

    @staticmethod
    def get_subjects_by_level(level_key: str) -> List[Tuple[str, str]]:
        subjects = PromptService.HIERARCHY_STRUCTURE.get(level_key, [])
        result = []
        for subj_key in subjects:
            i18n_key = f"subj_{subj_key}"
            label = t(i18n_key, default=subj_key)
            result.append((subj_key, label))
        return result

    @staticmethod
    def get_prompt_config(subject_key: str) -> dict:
        if subject_key not in PromptService._PROMPTS:
            if "math" in subject_key: return PromptService._PROMPTS.get("univ_math")
            return PromptService._PROMPTS.get("default")
        return PromptService._PROMPTS.get(subject_key)

