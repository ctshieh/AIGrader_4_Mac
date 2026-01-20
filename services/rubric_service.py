# services/rubric_service.py
# -*- coding: utf-8 -*-

from services.prompt_service import PromptService

class RubricService:
    @staticmethod
    def _resolve_granularity_logic(granularity: str) -> str:
        """
        [RESTORED] 從舊版 ai_service.py 還原：動態細緻度指令
        """
        return {
            "精簡": "Focus ONLY on the final result and core formula. Keep steps minimal (1-2 steps).",
            "標準": "Follow the standard point-to-step mapping provided in domain guidelines.",
            "診斷": "Maximum detail. Break down every possible algebraic step and reasoning."
        }.get(granularity, "Follow standard guidelines.")

    @staticmethod
    def get_rubric_generation_prompt(subject_key: str, granularity: str, language: str) -> str:
        """
        [RESTORED] 完整還原舊版 generate_rubric1 的 Prompt 邏輯、數學準則與 Schema。
        """
        
        # 1. [RESTORED] 領域規則字典 (完全來自您的舊程式碼)
        SUBJECT_GUIDELINES = {
            "Mathematics": r"""
            **STRICT MATHEMATICS / LINEAR ALGEBRA / STATISTICS RUBRIC GUIDELINES (University-level, STRICT):**

            1) **Adaptive Granularity (DO NOT be overly coarse or overly verbose)**:
               - Choose the number of rubric steps PER sub-question using BOTH point-value and complexity:
                 * ≤ 5 points: 2–3 steps
                 * 6–10 points: 3–5 steps
                 * 11–15 points: 5–7 steps
                 * 16–20 points: 6–8 steps
                 * > 20 points: 8–12 steps
               - Complexity adjustment:
                 * Single-line computation (e.g., det of 2x2, mean of small dataset): use the LOWER bound.
                 * One major transformation (e.g., one L'Hôpital / one RREF / one t-test): use the MIDDLE range.
                 * Multi-stage reasoning (multiple transformations or multi-part derivations): use the UPPER bound.

            2) **Strict Computation Policy (University grading)**:
               - For any step that involves calculation/derivation/simplification/substitution:
                 * If the key computation is WRONG, award **0** for that step.
                 * At most **1 point** may be awarded as "method recognition" ONLY when the method/setup is clearly correct.
               - A correct final answer with no supporting work gets **0** unless the problem explicitly states "answer-only allowed".

            3) **ECF (Error Carried Forward) DEFAULT = OFF**:
               - Only allow ECF when explicitly written in the criterion: "允許錯誤帶入(ECF)".
               - Even when ECF is allowed, NEVER award points for incorrect computations; ECF applies only to later logical steps using the student's previous result.

            4) **Criterion must be CHECKABLE (MANDATORY)**:
               - Each rubric item MUST be short and written in {language}.
               - Each rubric item MUST follow this template (single paragraph, no line breaks):
                 "（動作/要求）。需出現：<可檢核要素列表>。"
                 Optionally add: "若<常見錯誤>→此步0分。" or "允許錯誤帶入(ECF)。"
               - Avoid fancy Unicode math glyphs; keep plain text + LaTeX ($...$) only.

            5) **Statistics-specific notes**:
               - If an answer is numerical, specify acceptable rounding (e.g., to 3 decimals) and tolerance (e.g., ±0.001) in the criterion when appropriate.
               - Require both computation AND correct conclusion (reject / fail to reject H0) when applicable.

            6) **Linear Algebra-specific notes**:
               - Prefer checkable intermediate results (e.g., RREF, pivot columns, det, eigenpairs).

            7) **SymPy / SciPy Check Metadata (HIGHLY RECOMMENDED, and MANDATORY when applicable)**:
               - For each rubric item that involves a verifiable computation, include a `check` object.
               - `check.engine` should be one of: "sympy" (algebra/calculus/linear algebra) or "scipy" (statistics).
               - Keep expressions SymPy-friendly: use `log(x)` for ln(x), `exp(x)` for $e^x$, Use ASCII: `log(x)`, `exp(x)`, `**` for power,  `sin(x)`, `csc(x)`, `cot(x)`.
               - Example (derivative step): check={"engine":"sympy", "type":"derivative", "var":"x", "expr":"csc(x)", "expected":"-csc(x)*cot(x)"}.

               - Require explicit key objects: matrix, augmented matrix, row operations, RREF, pivot columns, solution set, eigenpairs, etc.
               - If a step claims a result (e.g., "RREF is ..."), it must be correct to receive points.
            
            8) **Definite Integrals (FTC Protocol)**:
               - Distinguish between Definite and Indefinite integrals.
               - Separate scoring: (A) Antiderivative Step $F(x)$. (B) Evaluation Step $F(b) - F(a)$.
               - Integrals MUST retain their limits $\int_a^b$ in all LaTeX.
            """,
            
            "Physics": r"""
            **STRICT PHYSICS RUBRIC:**
            1. **FBD**: Missing Free Body Diagram (FBD) = Deduction.
            2. **Units**: Answer without SI units = 0 points for the answer portion.
            3. **Variables**: Points for starting with symbolic variables before plugging in numbers.
            """,
            
            "Chemistry": r"""
            **STRICT CHEMISTRY RUBRIC:**
            1. **Stoichiometry**: Unbalanced equations = 0 points.
            2. **States of Matter**: Missing (s), (l), (g), (aq) where crucial = Deduction.
            3. **Sig Figs**: Answers must respect significant figures (if applicable).
            """,
            
            "Coding": r"""
            **STRICT CODING RUBRIC:**
            1. **Edge Cases**: Must handle boundary inputs (null, empty list, negative numbers).
            2. **Complexity**: Inefficient algorithms ($O(n^2)$ when $O(n)$ exists) = Partial credit.
            3. **Style**: Variable naming and indentation checks.
            """,
            
            "Essay": r"""
            **STRICT ESSAY RUBRIC:**
            1. **Thesis**: Must have a clear thesis statement.
            2. **Evidence**: Claims must be supported by specific examples.
            3. **Structure**: Logical flow and paragraph transitions.
            """
        }

        # 2. 選擇對應科目的規則
        # 這裡做了一個 mapping，將前端傳來的 key 對應到上面的 Dictionary
        if "math" in subject_key.lower() or "stat" in subject_key.lower():
            subject_focus = SUBJECT_GUIDELINES["Mathematics"].replace("{language}", language)
        elif "physics" in subject_key.lower():
            subject_focus = SUBJECT_GUIDELINES["Physics"]
        elif "chem" in subject_key.lower():
            subject_focus = SUBJECT_GUIDELINES["Chemistry"]
        elif "code" in subject_key.lower() or "program" in subject_key.lower():
            subject_focus = SUBJECT_GUIDELINES["Coding"]
        else:
            # 預設使用 Essay 或 Math 作為兜底
            subject_focus = SUBJECT_GUIDELINES.get("Essay", "")

        # 3. [RESTORED] 細緻度指令
        gran_logic = RubricService._resolve_granularity_logic(granularity)

        # 4. [RESTORED] 完整的 Prompt Template (包含 JSON Schema 與 LaTeX 規定)
        # 這裡的文字與您提供的 def generate_rubric1 內的 prompt 變數完全一致
        return f"""
        Act as a **Distinguished University Professor in {subject_key}**. Create a rigorous Answer Key and Grading Rubric.

        ### OBJECTIVE
        Analyze the **ATTACHED PDF EXAM** and generate a JSON rubric.

        ### DOMAIN FOCUS & STRICT RULES
        [GRADING STRATEGY]: {gran_logic}
        {subject_focus}

        ### INSTRUCTIONS (STRICT STEP-BY-STEP SCORING)

        1. **SOLVE** the problems in the PDF step-by-step clearly to derive the Ground Truth. All University level derivation and computation cannot be ommitted.

        2. **BREAK DOWN** scoring into granular partial credit steps (Adaptive step count per sub-question using the Guideline's table) (Follow the Domain Guidelines above):
           - **Concept**: Understanding the underlying principle.
           - **Setup**: Equations/diagrams/formulas setup.
           - **Execution**: Mathematical manipulation/Calculus steps.
           - **Answer**: Final result.

        3. **Step-by-Step Verification (Carry Forward Error)**:
           - Explicitly mark in the `description` or `criteria` that ECF is allowed for logical steps derived from previous errors.
        
        4. **Zero Tolerance for Magic Answers**:
           - If a complex problem has a correct final answer but no supporting work, the score is 0.

        5. **SUB-QUESTIONS (CRITICAL FORMAT)**: 
           - You MUST use the format **"1-1", "1-2"** (NOT "1a", "1b").
           - Example: If Question 1 has parts (a) and (b), their IDs must be "1-1" and "1-2".

        6. **FORMAT**: Output strict JSON.

        6.1 **RUBRIC STEP IDENTIFIERS (RECOMMENDED)**:
           - For each rubric item, include `rule_id` (e.g., "1-3.S2") and a short `title`.
           - Keep backward compatibility: still include `points` and `criterion`.

        6.2 **CHECK METADATA (MANDATORY when the step is computational and checkable)**:
           - For each rubric item that can be mechanically verified, include a `check` object.
           - Use SymPy-friendly expressions (ASCII): log(x), exp(x), sin(x), cos(x), tan(x), csc(x), sec(x), cot(x).
           - Typical `check` types:
             * derivative: {{"engine":"sympy","type":"derivative","var":"x","expr":"csc(x)","expected":"-csc(x)*cot(x)","policy":{{"all_or_nothing":true,"partial_credit_max":1}}}}
             * matrix_rref: {{"engine":"sympy","type":"matrix_rref","var":"x","input":{{"A":"[[1,2],[3,4]]"}},"expected":{{"rref":"[[1,0], [0,1]]"}}}}
             * det: {{"engine":"sympy","type":"det","input":{{"A":"[[1,2],[3,4]]"}},"expected":{{"value":"-2"}}}}
             * ttest_pvalue: {{"engine":"scipy","type":"ttest_pvalue","input":{{"xbar":12.3,"s":2.1,"n":25,"mu0":12,"alternative":"two-sided"}},"expected":{{"pvalue":0.43,"tol":0.001}}}}
           - If a step is purely conceptual and not mechanically checkable, you MAY omit `check`.

        6.3 **CALCULUS CHECK RULES (CRITICAL)**:
           - For **Intermediate Limits** (e.g., L'Hopital result, Simplification):
             The `expected` MUST be the algebraic expression, NOT the final number.
             * Example: If limit is -x -> 0.
             * Step "Simplification": expected="-x" (Check algebra).
             * Step "Final Answer": expected="0" (Check value).
             
           - For **L'Hopital's Rule**:
             The `expected` MUST be the fraction of derivatives.
             * correct: "(1/x)/(-1/x**2)" or simplified "-x".
             * INCORRECT: "1/x" (Numerator only) -> This causes grading errors.

        7. **[LATEX FORMATTING - MANDATORY]**:
           - **ALL mathematical expressions MUST be wrapped in LaTeX delimiters ($...$).**
           - **Correct**: "The integral is $\\int x^2 dx$."
           - **Incorrect**: "The integral is \int x^2 dx" or "The integral is x^2".
           - This applies to `description`, `criteria`, and any text field in the JSON.

        ### OUTPUT LANGUAGE
        **STRICTLY OUTPUT THE CONTENT IN {language}.**

        ### OUTPUT JSON SCHEMA (STRICT FOLLOW)
        {{
          "exam_title": "Exam Name",
          "total_points": 100,
          "questions": [
            {{
              "id": "1",
              "points": 15,
              "description": "Calculate the limit: $\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}}$... (Full question text with LaTeX)",
              "sub_questions": [
                {{
                    "id": "1-1", 
                    "points": 5, 
                    "description": "Evaluate limit",
                    "rubric": [
                        {{ 
                            "rule_id":"1-1.S1",
                            "title":"方法辨識",
                            "points": 2, 
                            "criterion": "正確辨識方法。需出現：$...$。", 
                            "check": {{"engine":"sympy","type":"derivative","var":"x","expr":"log(x)","expected":"1/x","policy":{{"all_or_nothing":true,"partial_credit_max":1}}}} 
                        }},
                        {{ "points": 2, "criterion": "Derivative calculation: $\\cos x$" }},
                        {{ "points": 1, "criterion": " $1$" }}
                    ]
                }}
              ]
            }}
          ]
        }}
        """.strip()
