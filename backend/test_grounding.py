"""
Deterministic test suite for factual grounding and claim-level unsupported-content detection.
Covers CyberShield source text, supported paraphrasing, scaffolding filtering,
unsupported qualitative/quantitative hallucinations, and existing metric regression tests.
"""

import unittest
from unittest.mock import MagicMock
from schemas.transform_schema import TransformRequest, RefineRequest, CanonicalContentModel
from services.transform_service import (
    verify_factual_grounding,
    validate_output,
    extract_key_factual_tokens,
    _stem_word,
    _is_scaffolding_or_boilerplate,
    _split_into_claim_candidates,
    build_recovery_prompt,
    should_trigger_recovery,
    validate_and_recover_outputs,
    build_canonical_content_model,
    mock_transform_content,
    mock_refine_content,
    validate_cross_format_consistency,
    calculate_quality_score,
    evaluate_quality_gate,
    build_claim_level_provenance
)

CYBERSHIELD_SOURCE = (
    "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026 to "
    "safeguard cloud infrastructure, identify zero-day vulnerabilities, and ensure zero-trust compliance "
    "across distributed multi-cloud environments. During internal pilot testing, automated detection "
    "reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral "
    "movement occurred. Key pillars include real-time anomaly detection, automated policy enforcement, "
    "continuous posture management, and seamless CI/CD security scanning. The platform has received "
    "SOC2 Type II certification and adheres to ISO/IEC 27001 standards."
)


class TestStemmerAndScaffoldingFilter(unittest.TestCase):
    """Tests the zero-dependency suffix normalizer and structural filtering."""

    def test_suffix_stemming(self):
        # Morphological variants that appear in paraphrases
        self.assertEqual(_stem_word("migration"), _stem_word("migrating"))
        self.assertEqual(_stem_word("reduced"), _stem_word("reducing"))
        self.assertEqual(_stem_word("enforcement"), _stem_word("enforces"))
        self.assertEqual(_stem_word("management"), _stem_word("managing"))
        self.assertEqual(_stem_word("detection"), _stem_word("detecting"))

    def test_scaffolding_and_boilerplate_detection(self):
        # Markdown headers
        self.assertTrue(_is_scaffolding_or_boilerplate("## Executive Summary"))
        self.assertTrue(_is_scaffolding_or_boilerplate("# Key Insights"))
        self.assertTrue(_is_scaffolding_or_boilerplate("### Architecture Overview"))
        
        # Slide and scene indicators
        self.assertTrue(_is_scaffolding_or_boilerplate("Slide 1: Overview"))
        self.assertTrue(_is_scaffolding_or_boilerplate("Scene 2: Demonstration"))
        self.assertTrue(_is_scaffolding_or_boilerplate("Speaker Notes: Presenter guidance"))
        
        # Social media hooks and CTAs
        self.assertTrue(_is_scaffolding_or_boilerplate("What do you think? Drop your thoughts below."))
        self.assertTrue(_is_scaffolding_or_boilerplate("Follow for more updates!"))
        self.assertTrue(_is_scaffolding_or_boilerplate("Read the full report."))
        self.assertTrue(_is_scaffolding_or_boilerplate("#CyberShield #ZeroTrust #CloudSecurity"))
        
        # Substantive factual claims should NOT be filtered
        self.assertFalse(_is_scaffolding_or_boilerplate(
            "Automated detection reduced threat response times by 68%."
        ))
        self.assertFalse(_is_scaffolding_or_boilerplate(
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards."
        ))


class TestCyberShieldSupportedParaphrasing(unittest.TestCase):
    """Verifies that normal paraphrasing, synthesis, and formatting are NOT falsely flagged."""

    def test_direct_paraphrase_grounded(self):
        output = (
            "Under Project CyberShield, automated detection reduced threat response times by 68% "
            "while mitigating 99.4% of simulated intrusions before lateral movement."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(result["is_grounded"], f"Failed: {result}")
        self.assertEqual(len(result["unsupported_claims"]), 0)
        self.assertIn("68%", result["cited_facts"])
        self.assertIn("99.4%", result["cited_facts"])
        self.assertEqual(len(result["unverified_metrics"]), 0)

    def test_morphological_paraphrase_grounded(self):
        output = (
            "The platform enforces continuous posture management and automated scanning across "
            "CI/CD pipelines to ensure zero-trust compliance."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(result["is_grounded"], f"Failed: {result}")
        self.assertEqual(len(result["unsupported_claims"]), 0)
        self.assertGreaterEqual(result["claim_grounding_score"], 0.9)

    def test_multi_sentence_synthesis_grounded(self):
        output = (
            "Initiated in Q1 2026, the CyberShield framework achieved SOC2 Type II and "
            "ISO/IEC 27001 certifications while protecting distributed multi-cloud infrastructure."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(result["is_grounded"], f"Failed: {result}")
        self.assertEqual(len(result["unsupported_claims"]), 0)

    def test_scaffolding_and_formatting_not_flagged(self):
        output = (
            "## Executive Summary: Project CyberShield\n\n"
            "Key Pillars & Architecture:\n"
            "* Real-time anomaly detection and continuous posture management.\n"
            "* Seamless CI/CD security scanning.\n\n"
            "Slide 1: Overview & Certification\n"
            "Speaker Notes: Emphasize SOC2 Type II compliance.\n\n"
            "What do you think about these results? Drop your thoughts below.\n"
            "#CyberSecurity #ZeroTrust #CloudSecurity"
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(result["is_grounded"], f"Failed: {result}")
        self.assertEqual(len(result["unsupported_claims"]), 0)


class TestCyberShieldUnsupportedDetection(unittest.TestCase):
    """Verifies that ungrounded/hallucinated content is reliably flagged."""

    def test_fabricated_acquisition_flagged(self):
        output = (
            "CyberShield was acquired by a European aerospace conglomerate and the "
            "CEO announced a complete shutdown of European operations."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(result["is_grounded"])
        self.assertGreaterEqual(len(result["unsupported_claims"]), 1)
        self.assertIn("unsupported claim(s) detected", result["summary"])

    def test_fabricated_foreign_initiative_flagged(self):
        output = (
            "The team also launched a quantum-resistant cryptography module in "
            "partnership with Tokyo University."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(result["is_grounded"])
        self.assertGreaterEqual(len(result["unsupported_claims"]), 1)

    def test_fabricated_layoffs_flagged(self):
        output = (
            "Additionally, the engineering division laid off 400 contractors to "
            "fund autonomous AI drones."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(result["is_grounded"])
        self.assertGreaterEqual(len(result["unsupported_claims"]), 1)

    def test_unverified_metrics_flagged(self):
        output = (
            "During internal pilot testing, automated detection reduced threat response times "
            "by 95%, saving $12M in operational damages."
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(result["is_grounded"])
        # Should flag unverified metrics
        self.assertIn("95%", result["unverified_metrics"])
        self.assertTrue(any("$12" in m for m in result["unverified_metrics"]))

    def test_mixed_grounded_and_ungrounded_document(self):
        output = (
            "## Executive Summary\n"
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n"
            "Automated detection reduced threat response times by 68% and stopped 99.4% of intrusions.\n"
            "Additionally, the company acquired a German robotics startup in Munich for $50M.\n"
        )
        result = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(result["is_grounded"])
        # Exactly the 3rd sentence should be flagged as unsupported
        self.assertEqual(len(result["unsupported_claims"]), 1)
        self.assertIn("robotics startup in Munich", result["unsupported_claims"][0])
        # Metrics verified and unverified
        self.assertIn("68%", result["cited_facts"])
        self.assertIn("99.4%", result["cited_facts"])
        self.assertIn("$50m", result["unverified_metrics"])

    def test_hallucinated_acquisition_german_firm_regression(self):
        """
        Regression test: Verify that the exact hallucinated claim is strictly rejected
        with currency, event, and compound entity validation.
        """
        claim = "The strategic acquisition of a German cybersecurity firm for $12 million in Q1 2026 bolsters the framework's core capabilities."
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, claim)

        # Expected results:
        # - is_grounded = false
        # - "$12 million" = unverified metric
        # - acquisition = unsupported event
        # - German cybersecurity firm = unsupported entity/fact
        self.assertFalse(res["is_grounded"])
        self.assertIn("$12 million", res["unverified_metrics"])
        self.assertIn("acquisition", res["unsupported_events"])
        self.assertIn("German cybersecurity firm", res["unsupported_entities"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)
        self.assertEqual(res["claim_grounding_score"], 0.0)
        self.assertIn("ungrounded content detected", res["summary"])

    def test_currency_extraction_and_equivalence_variants(self):
        """
        Verify currency extraction captures complete monetary facts:
        '$12 million', 'USD 12 million', '$12M', '$12,000,000'.
        """
        variants = ["$12 million", "USD 12 million", "$12M", "$12,000,000"]
        for curr in variants:
            sample = f"The strategic buyout was completed for {curr} in Q1 2026."
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, sample)
            self.assertFalse(res["is_grounded"], f"Failed to reject ungrounded currency {curr}")
            self.assertTrue(
                any("$12" in m or "12" in m or "usd 12" in m.lower() for m in res["unverified_metrics"]),
                f"Currency {curr} not in unverified metrics: {res['unverified_metrics']}"
            )

    def test_source_fact_coverage_separated_from_grounding(self):
        """
        Verify that 8/8 (100%) source fact coverage does NOT automatically mean grounded
        if an ungrounded claim is present in the output.
        """
        doc = (
            "Project CyberShield is an enterprise framework initiated in Q1 2026 to ensure zero-trust compliance. "
            "Automated detection reduced threat response times by 68% and stopped 99.4% of intrusions. "
            "Key pillars include real-time anomaly detection and CI/CD security scanning. "
            "The platform received SOC2 Type II certification and adheres to ISO/IEC 27001 standards. "
            "The strategic acquisition of a German cybersecurity firm for $12 million in Q1 2026 bolsters the framework's core capabilities."
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, doc)
        self.assertEqual(res["verified_count"], res["total_source_facts"])
        self.assertIn("100.0%", res["source_fact_coverage"])
        self.assertFalse(res["is_grounded"], "100% source coverage must NOT mean grounded when hallucination present")
        self.assertIn("$12 million", res["unverified_metrics"])
        self.assertIn("acquisition", res["unsupported_events"])
        self.assertIn("German cybersecurity firm", res["unsupported_entities"])

    def test_context_aware_acquisition_event_detection_regression(self):
        """
        Regression test: Proves context-aware corporate acquisition detection:
        - 'acquisition of a German cybersecurity firm' is flagged as an unsupported corporate acquisition event.
        - 'acquisition of SOC2 Type II certification' refers to credential attainment and is NOT flagged.
        """
        # 1. Genuinely unsupported corporate acquisition of a company/firm MUST be flagged
        corp_claim = "The strategic acquisition of a German cybersecurity firm bolsters the framework's core capabilities."
        res_corp = verify_factual_grounding(CYBERSHIELD_SOURCE, corp_claim)
        self.assertFalse(res_corp["is_grounded"])
        self.assertIn("acquisition", res_corp["unsupported_events"])
        self.assertIn("German cybersecurity firm", res_corp["unsupported_entities"])

        # 2. Acquisition of SOC2 Type II certification MUST NOT be flagged as unsupported event
        cred_claim = (
            "Regulatory and compliance standings were significantly strengthened, highlighted by the "
            "successful acquisition of SOC2 Type II certification and full adherence to ISO/IEC 27001 standards."
        )
        res_cred = verify_factual_grounding(CYBERSHIELD_SOURCE, cred_claim)
        self.assertTrue(res_cred["is_grounded"], f"False positive on credential acquisition: {res_cred}")
        self.assertNotIn("acquisition", res_cred["unsupported_events"])
        self.assertEqual(len(res_cred["unsupported_events"]), 0)
        self.assertEqual(len(res_cred["unsupported_claims"]), 0)

    def test_unsupported_causal_and_qualitative_claims_rejected(self):
        """
        Regression test: Proves that unsupported causal implications and unstated qualitative conclusions
        are rejected as unsupported claims by factual grounding, while source-faithful statements are accepted.
        """
        # 1. Qualitative claims with ungrounded conclusions must be flagged as unsupported
        qual_claim = "Internal pilot testing data indicates substantial operational and defensive gains."
        res_qual = verify_factual_grounding(CYBERSHIELD_SOURCE, qual_claim)
        self.assertFalse(res_qual["is_grounded"])
        self.assertIn(qual_claim, res_qual["unsupported_claims"])

        # 2. Causal claims asserting unstated outcomes/benefits must be flagged as unsupported
        causal_claim = (
            "The implementation yielded a 68% reduction in threat response times, "
            "directly enhancing operational efficiency and incident containment."
        )
        res_causal = verify_factual_grounding(CYBERSHIELD_SOURCE, causal_claim)
        self.assertFalse(res_causal["is_grounded"])
        self.assertIn(causal_claim, res_causal["unsupported_claims"])

        # 3. Source-faithful statement without invented causal implications is accepted as grounded
        faithful_claim = (
            "Internal pilot testing showed a 68% reduction in threat response times "
            "through automated detection mechanisms."
        )
        res_faithful = verify_factual_grounding(CYBERSHIELD_SOURCE, faithful_claim)
        self.assertTrue(res_faithful["is_grounded"], f"Faithful claim falsely rejected: {res_faithful}")
        self.assertEqual(len(res_faithful["unsupported_claims"]), 0)


class TestGroundingRegressionAndHardening(unittest.TestCase):
    """Preserves all existing token-level regression behaviors and edge cases."""

    def test_empty_or_none_inputs(self):
        res1 = verify_factual_grounding("", "Some text")
        self.assertTrue(res1["is_grounded"])
        self.assertEqual(res1["verified_count"], 0)

        res2 = verify_factual_grounding("Some source", "")
        self.assertTrue(res2["is_grounded"])
        self.assertEqual(res2["verified_count"], 0)

    def test_multimodal_source_bypass(self):
        visual_src = "[Visual Source: Architectural Diagram showing 3 tiers and 10MB cache]"
        output = "The system uses 3 tiers and 10MB cache."
        res = verify_factual_grounding(visual_src, output)
        self.assertTrue(res["is_grounded"])
        self.assertEqual(len(res["unverified_metrics"]), 0)
        self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_factual_token_extraction(self):
        sample = "In Q2 2026, revenue was $42.5M, up 28% with 3.8x speedup and SOC 2 / ISO 27001 compliance."
        tokens = extract_key_factual_tokens(sample)
        self.assertIn("q22026", tokens)
        self.assertIn("2026", tokens)
        self.assertIn("$42.5m", tokens)
        self.assertIn("28%", tokens)
        self.assertIn("3.8x", tokens)
        self.assertIn("SOC2", tokens)
        self.assertIn("ISO27001", tokens)

    def test_validate_output_integration_clean(self):
        output = (
            "Executive Summary:\n"
            "Project CyberShield is an enterprise framework initiated in Q1 2026. "
            "Threat response times fell by 68% during internal pilot testing."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=output,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertIn(val["severity"], ("none", "warning"))
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_validate_output_integration_with_unsupported_claim(self):
        output = (
            "Executive Summary Overview:\n"
            "Project CyberShield was initiated in Q1 2026 to safeguard cloud infrastructure.\n"
            "The company announced an immediate acquisition of a German robotics startup in Munich."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=output,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])  # Stays valid without crashing
        self.assertEqual(val["severity"], "warning")
        self.assertFalse(val["factual_grounding"]["is_grounded"])
        self.assertTrue(any("unsupported" in issue.lower() for issue in val["issues"]))

    def test_pure_qualitative_hallucination_without_numbers(self):
        # A completely qualitative hallucination without any numerical metrics
        output = (
            "The board of directors voted unanimously to dissolve the cybersecurity unit "
            "and transfer all assets to a foundation in Switzerland."
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertEqual(len(res["unverified_metrics"]), 0)  # No numbers
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)  # Caught by claim verifier
        self.assertIn("unsupported claim(s) detected", res["summary"])

    def test_social_linkedin_post_grounding(self):
        output = (
            "🛡️ Enterprise Cybersecurity Update:\n\n"
            "During internal pilot testing of Project CyberShield, automated detection reduced threat response times by 68% "
            "and blocked 99.4% of intrusions!\n\n"
            "The platform has achieved SOC2 Type II certification and aligns with ISO/IEC 27001.\n\n"
            "What is your organization doing to advance zero-trust security? Let us know below!\n\n"
            "#CyberSecurity #CloudSecurity #DevOps #ZeroTrust"
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Failed: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertIn("68%", res["cited_facts"])

    def test_infographic_blueprint_grounding(self):
        output = (
            "Infographic Blueprint: Project CyberShield Architecture\n\n"
            "Visual Layout: 3-column split view with top stat banner\n"
            "Header Metric: 68% Reduction in Threat Response Time\n"
            "Key Metric: 99.4% Intrusions Mitigated Prior to Lateral Movement\n\n"
            "Pillar 1: Real-time anomaly detection and policy enforcement\n"
            "Pillar 2: Continuous posture management and CI/CD security scanning\n"
            "Pillar 3: SOC2 Type II & ISO/IEC 27001 Compliance\n\n"
            "Icon: Shield in cobalt blue"
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Failed: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_provenance_structure_backward_compatibility(self):
        from services.transform_service import build_output_provenance
        output = "Automated detection reduced threat response times by 68%."
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=output,
            source_content=CYBERSHIELD_SOURCE
        )
        prov = build_output_provenance(
            output_type="LinkedIn Post",
            generation_action="generated",
            call_architecture="consolidated_single_call",
            model="gemini-3.5-flash-lite",
            is_mock=True,
            source_reference="Project_CyberShield_Audit_Q1_2026.pdf",
            validation=val
        )
        self.assertIn("factual_grounding", prov)
        fg = prov["factual_grounding"]
        # Verify backward compatibility fields
        self.assertIn("is_grounded", fg)
        self.assertIn("verified_count", fg)
        self.assertIn("total_source_facts", fg)
        self.assertIn("cited_facts", fg)
        self.assertIn("unverified_metrics", fg)
        self.assertIn("summary", fg)
        # Verify new claim-level fields
        self.assertIn("total_claims", fg)
        self.assertIn("supported_claims_count", fg)
        self.assertIn("unsupported_claims", fg)
        self.assertIn("claim_grounding_score", fg)


class TestScaffoldingAndActionExclusionHardening(unittest.TestCase):
    """
    Regression tests verifying that action directives, production recommendations,
    metadata labels, and transitional phrases are excluded from false positive claim detection,
    while still enforcing metric verification and genuine hallucination detection.
    """

    def test_action_recommendation_statements_excluded_from_false_positives(self):
        actions = [
            "Proceed with full-scale deployment across enterprise cloud environments.",
            "Integrate automated security scans into all CI/CD pipelines.",
            "Utilize centralized compliance dashboards for real-time visibility.",
            "Security Teams must review audit logs weekly to maintain posture.",
            "Engineering Leadership must prioritize automated regression testing.",
            "Compliance Officers must ensure continuous alignment with SOC2 standards."
        ]
        for act in actions:
            self.assertTrue(
                _is_scaffolding_or_boilerplate(act),
                f"Action statement falsely classified as substantive factual claim: '{act}'"
            )
            # When evaluated against CyberShield, none should be flagged as unsupported
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, act)
            self.assertTrue(res["is_grounded"], f"Action falsely ungrounded: {act} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_production_design_recommendations_excluded_from_false_positives(self):
        design_cues = [
            "Music Mood: Ambient, forward-looking tech pulse with subtle acoustic layers.",
            "Pacing: Energetic and brisk, with scene transitions every 3-5 seconds.",
            "Visual Style: Clean enterprise minimalist aesthetic with glassmorphic cards.",
            "Chart Ideas: 3D bar chart contrasting threat detection latency before and after.",
            "Suggested Icons: Glowing blue security shield, network nodes, CI/CD pipeline gears.",
            "Color/Design Hierarchy: Deep slate navy primary with electric cobalt accents."
        ]
        for cue in design_cues:
            self.assertTrue(
                _is_scaffolding_or_boilerplate(cue),
                f"Design recommendation falsely classified as substantive factual claim: '{cue}'"
            )
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, cue)
            self.assertTrue(res["is_grounded"], f"Design cue falsely ungrounded: {cue} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_output_metadata_and_instructions_excluded_from_false_positives(self):
        metadata_lines = [
            "Target Duration: 75 seconds",
            "Objective: Inform executive leadership regarding enterprise security transformation.",
            "Production Recommendations:",
            "Next Steps:",
            "Action Items:"
        ]
        for meta in metadata_lines:
            self.assertTrue(
                _is_scaffolding_or_boilerplate(meta),
                f"Metadata line falsely classified as substantive factual claim: '{meta}'"
            )
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, meta)
            self.assertTrue(res["is_grounded"], f"Metadata falsely ungrounded: {meta} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_transitional_leadin_phrases_excluded_from_false_positives(self):
        transitions = [
            "Our recent pilot testing delivered compelling data-driven results:",
            "Today we present the core architecture powering Project CyberShield."
        ]
        for trans in transitions:
            self.assertTrue(
                _is_scaffolding_or_boilerplate(trans),
                f"Transitional lead-in falsely classified as substantive factual claim: '{trans}'"
            )
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, trans)
            self.assertTrue(res["is_grounded"], f"Transition falsely ungrounded: {trans} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_recommendation_with_ungrounded_metric_still_flagged(self):
        # Even though "Proceed with" is an action verb, 70% is NOT in the source (source has 68%)
        output = (
            "Proceed with full-scale deployment to achieve 70% latency reduction across all clusters."
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("70%", res["unverified_metrics"])
        self.assertIn("70%", res["summary"])

    def test_invented_70_percent_metric_still_flagged(self):
        # Direct factual statement claiming 70% instead of 68%
        output = "The framework reduced threat response times by 70%."
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("70%", res["unverified_metrics"])

    def test_recommendation_with_hallucinated_acquisition_still_flagged(self):
        # A directive asserting an invented historical fact (acquisition) must NOT escape detection
        output = "Proceed with full-scale deployment following the acquisition of Munich Robotics."
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)
        self.assertIn("Munich Robotics", res["unsupported_claims"][0])

    def test_comprehensive_artefact_with_recommendations_and_metadata_grounded(self):
        output = (
            "# Executive Briefing: Project CyberShield\n\n"
            "Objective: Inform executive leadership regarding enterprise security transformation.\n"
            "Target Duration: 75 seconds\n\n"
            "Today we present the core architecture powering Project CyberShield.\n"
            "Our recent pilot testing delivered compelling data-driven results:\n\n"
            "During internal pilot testing, automated detection reduced threat response times by 68%, "
            "mitigating 99.4% of simulated intrusions.\n"
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.\n\n"
            "Production Recommendations:\n"
            "Visual Style: Clean enterprise minimalist aesthetic with glassmorphic cards.\n"
            "Suggested Icons: Glowing blue security shield, network nodes, CI/CD pipeline gears.\n"
            "Music Mood: Ambient, forward-looking tech pulse with subtle acoustic layers.\n\n"
            "Action Items & Next Steps:\n"
            "* Proceed with full-scale deployment across all enterprise cloud environments.\n"
            "* Integrate automated security scanning into all CI/CD pipelines.\n"
            "* Security Teams must review audit logs weekly to maintain posture.\n"
            "* Compliance Officers must ensure continuous alignment with SOC2 standards.\n"
        )
        res = verify_factual_grounding(CYBERSHIELD_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Comprehensive artefact falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)
        self.assertIn("68%", res["cited_facts"])
        self.assertIn("99.4%", res["cited_facts"])
        self.assertIn("SOC2", res["cited_facts"])

    def test_compound_stakeholders_and_directives_excluded(self):
        cases = [
            "All business units and technical teams must integrate continuous posture management.",
            "Engineering and technical teams must collaborate on CI/CD pipelines.",
            "Executive leadership and compliance officers must establish zero-trust policies.",
            "Security Operations (SecOps): Implement real-time anomaly detection.",
            "For all engineering teams, the directive is active: implement real-time anomaly detection.",
            "The directive is clear: strengthen multi-cloud security controls."
        ]
        for c in cases:
            self.assertTrue(_is_scaffolding_or_boilerplate(c), f"Scaffolding missed: {c}")
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, c)
            self.assertTrue(res["is_grounded"], f"Falsely ungrounded: {c} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_passive_prescriptive_obligations_and_risk_framing_excluded(self):
        cases = [
            "Operational deployment is now required across all enterprise cloud environments.",
            "Adherence to zero-trust standards is mandated for all engineering units.",
            "Operating without these controls exposes multi-cloud infrastructure to zero-day vulnerabilities.",
            "Unsecured CI/CD pipelines remain prime vectors for zero-day exploits.",
            "This drastically reduces organizational exposure to unauthorized lateral movement."
        ]
        for c in cases:
            self.assertTrue(_is_scaffolding_or_boilerplate(c), f"Scaffolding missed: {c}")
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, c)
            self.assertTrue(res["is_grounded"], f"Falsely ungrounded: {c} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_visual_infographic_and_agenda_scaffolding_excluded(self):
        cases = [
            "Central Hub: The 4 Core Pillars of Project CyberShield",
            "Data Impact Section: High-contrast statistical callouts displaying pilot metrics.",
            "Donut Chart: Showing 68% reduction in threat response time.",
            "Operational Impact & Pilot Results",
            "Strategic Deployment & Next Steps"
        ]
        for c in cases:
            self.assertTrue(_is_scaffolding_or_boilerplate(c), f"Scaffolding missed: {c}")
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, c)
            self.assertTrue(res["is_grounded"], f"Falsely ungrounded: {c} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_social_and_leadership_ctas_excluded(self):
        cases = [
            "It is time for executive leadership to prioritize continuous posture management.",
            "We call upon all engineering practitioners to establish automated security scanning."
        ]
        for c in cases:
            self.assertTrue(_is_scaffolding_or_boilerplate(c), f"Scaffolding missed: {c}")
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, c)
            self.assertTrue(res["is_grounded"], f"Falsely ungrounded: {c} -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_qualitative_hallucinations_in_actions_and_narratives_still_flagged(self):
        # Genuine qualitative hallucinations must be reliably caught
        hallucinations = [
            "CyberShield acquired a robotics company in Munich.",
            "CyberShield announced a strategic partnership with Munich Robotics.",
            "Engineering Leadership announced the acquisition of Munich Robotics.",
            "The team partnered with Tokyo University to implement quantum scanning.",
            "The board voted to dissolve the cybersecurity unit and transfer assets to Switzerland."
        ]
        for h in hallucinations:
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, h)
            self.assertFalse(res["is_grounded"], f"Hallucination failed to trigger ungrounded flag: '{h}'")
            self.assertGreaterEqual(
                len(res["unsupported_claims"]), 1,
                f"Expected unsupported claim for '{h}', got: {res}"
            )

    def test_morphological_variants_at_sentence_start_not_flagged(self):
        # Morphological capitalized words like 'Mitigated' must not trigger false positive foreign entity checks
        valid_sentences = [
            "Mitigated 99.4% of intrusions prior to lateral movement.",
            "Mitigated prior to lateral movement across cloud environments."
        ]
        for s in valid_sentences:
            res = verify_factual_grounding(CYBERSHIELD_SOURCE, s)
            self.assertTrue(res["is_grounded"], f"Morphological variant falsely ungrounded: '{s}' -> {res}")
            self.assertEqual(len(res["unsupported_claims"]), 0)



COLLEGE_ATTENDANCE_SOURCE = (
    "In 2026, our college introduced a digital attendance system featuring real-time attendance records and automated notifications to students. "
    "During the first semester, attendance processing time decreased by 40%."
)


class TestLinkedInGroundingRegression(unittest.TestCase):
    """
    Regression tests specifically validating factual grounding constraints for LinkedIn Posts
    using the college attendance source.
    """

    def test_case_a_unsupported_broader_hook_ungrounded(self):
        # Case A: "Optimizing institutional operations through digital transformation yields measurable returns." -> must be ungrounded
        claim_a = "Optimizing institutional operations through digital transformation yields measurable returns."
        res = verify_factual_grounding(COLLEGE_ATTENDANCE_SOURCE, claim_a)
        self.assertFalse(res["is_grounded"], f"Case A should be ungrounded: {res}")
        self.assertIn(claim_a, res["unsupported_claims"])

    def test_case_b_operational_efficiency_extrapolation_not_supported(self):
        # Case B: "#OperationalEfficiency" / equivalent claim involving operational efficiency
        # should not be treated as a supported source concept when source only says processing time decreased by 40%
        self.assertNotIn("operational efficiency", COLLEGE_ATTENDANCE_SOURCE.lower())

        claims = [
            "The implementation delivered improved operational efficiency across campus.",
            "This initiative improved operational efficiency for the college.",
            "Digital attendance systems deliver superior operational efficiency and organizational productivity.",
            "The new system maximizes operational efficiency."
        ]
        for c in claims:
            res = verify_factual_grounding(COLLEGE_ATTENDANCE_SOURCE, c)
            self.assertFalse(res["is_grounded"], f"Operational efficiency claim should be ungrounded: '{c}' -> {res}")
            self.assertIn(c, res["unsupported_claims"])

    def test_case_c_source_faithful_statement_grounded(self):
        # Case C: A source-faithful LinkedIn statement such as:
        # "Our college introduced a digital attendance system in 2026, and attendance processing time decreased by 40% during the first semester."
        # -> must remain grounded.
        claim_c = (
            "Our college introduced a digital attendance system in 2026, and attendance "
            "processing time decreased by 40% during the first semester."
        )
        res = verify_factual_grounding(COLLEGE_ATTENDANCE_SOURCE, claim_c)
        self.assertTrue(res["is_grounded"], f"Case C should be grounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)
        self.assertEqual(len(res["unsupported_events"]), 0)
        self.assertIn("40%", res["cited_facts"])
        self.assertIn("2026", res["cited_facts"])



CLINICAL_TRIAL_SOURCE = (
    "In a 2025 multi-center clinical study involving 450 adult patients, the CardioPulse remote monitoring device "
    "reduced hospital readmission rates by 32% over a six-month follow-up period. The system transmits continuous ECG telemetry "
    "and alerts on-call clinicians to cardiac arrhythmias in real time. The device received FDA 510(k) clearance in October 2025."
)

SOLAR_GRID_SOURCE = (
    "HelioGrid completed the installation of its smart photovoltaic microgrid at the Mojave Desert facility in August 2025. "
    "During peak daylight hours, the 50-megawatt solar array met 85% of local auxiliary power demands while reducing grid transmission losses by 18%. "
    "The facility utilizes lithium-iron-phosphate battery storage with automated load switching and conforms to IEEE 1547 interconnection standards."
)


class TestMultiFormatSourceAgnosticGroundingRegression(unittest.TestCase):
    """
    Validates factual grounding across Advisory, Twitter/X Post, Infographic,
    Presentation, and Video Package formats across two different fictional sources.
    """

    # --- 1. ADVISORY TESTS (using CLINICAL_TRIAL_SOURCE) ---
    def test_advisory_source_faithful_grounded(self):
        output = (
            "Advisory: Clinical Implementation of CardioPulse Remote Monitoring\n"
            "Context: In a 2025 clinical study involving 450 adult patients, the CardioPulse remote monitoring device demonstrated a 32% reduction in hospital readmission rates over six months.\n"
            "Operational Impact: The system transmits continuous ECG telemetry and alerts on-call clinicians to cardiac arrhythmias in real time.\n"
            "Regulatory Directives: Clinical teams must follow device protocols following FDA 510(k) clearance in October 2025."
        )
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Faithful advisory falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)

    def test_advisory_invented_metric_rejected(self):
        output = "Advisory: The CardioPulse device reduced hospital readmission rates by 75% across participating health networks."
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("75%", res["unverified_metrics"])

    def test_advisory_invented_event_entity_rejected(self):
        output = "Advisory: CardioPulse announced the acquisition of Zurich Biosensors to expand European clinical operations."
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertTrue("acquisition" in res["unsupported_events"] or len(res["unsupported_claims"]) > 0)

    def test_advisory_unsupported_causal_benefit_rejected(self):
        output = "Advisory: Remote monitoring directly eliminated emergency surgical interventions and generated $12M in hospital cost savings."
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertTrue(len(res["unsupported_claims"]) > 0 or len(res["unverified_metrics"]) > 0)

    # --- 2. TWITTER/X POST TESTS (using CLINICAL_TRIAL_SOURCE) ---
    def test_twitter_source_faithful_grounded(self):
        output = (
            "1/2: In a 2025 study of 450 adult patients, the CardioPulse remote monitoring device reduced hospital readmission rates by 32% over six months.\n"
            "2/2: The system transmits continuous ECG telemetry with real-time arrhythmia alerts and holds FDA 510(k) clearance from October 2025. #CardioPulse #FDA"
        )
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Faithful Twitter post falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)

    def test_twitter_invented_metric_rejected(self):
        output = "CardioPulse cut patient mortality by 65% across 1,200 intensive care units nationwide. #CardioPulse"
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("65%", res["unverified_metrics"])

    def test_twitter_invented_event_rejected(self):
        output = "CardioPulse finalized a merger with Boston Surgical to monopolize cardiac telemetry."
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("merger", res["unsupported_events"])

    def test_twitter_unsupported_benefit_rejected(self):
        output = "CardioPulse completely revolutionized patient longevity through digital healthcare transformation."
        res = verify_factual_grounding(CLINICAL_TRIAL_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)

    # --- 3. INFOGRAPHIC TESTS (using SOLAR_GRID_SOURCE) ---
    def test_infographic_source_faithful_grounded(self):
        output = (
            "Infographic Specification: HelioGrid Mojave Desert Microgrid\n"
            "Core Message: HelioGrid installed a smart photovoltaic microgrid at the Mojave Desert facility in August 2025.\n"
            "Key Points & Verified Statistics:\n"
            "• 50-megawatt solar array capacity installed in August 2025.\n"
            "• Met 85% of local auxiliary power demands during peak daylight hours.\n"
            "• Grid transmission losses decreased by 18%.\n"
            "• Conforms to IEEE 1547 interconnection standards with lithium-iron-phosphate battery storage.\n"
            "Visual Recommendations: Bar chart illustrating 85% auxiliary demand coverage and 18% transmission loss reduction."
        )
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Faithful infographic falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)

    def test_infographic_invented_metric_rejected(self):
        output = "Data Pillar 1: The solar facility reduced carbon emissions by 94% in the first quarter."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("94%", res["unverified_metrics"])

    def test_infographic_invented_entity_event_rejected(self):
        output = "HelioGrid entered into an enterprise partnership with Nevada Power Corp for regional distribution."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("partnership", res["unsupported_events"])

    def test_infographic_unsupported_benefit_rejected(self):
        output = "The microgrid installation achieved complete commercial energy independence for the regional power authority."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)

    # --- 4. PRESENTATION TESTS (using SOLAR_GRID_SOURCE) ---
    def test_presentation_source_faithful_grounded(self):
        output = (
            "Slide 1: HelioGrid Mojave Desert Facility Overview\n"
            "• HelioGrid completed installation of its smart photovoltaic microgrid at the Mojave Desert facility in August 2025.\n"
            "• System features lithium-iron-phosphate battery storage with automated load switching.\n"
            "Slide 2: Operating Performance & Interconnection\n"
            "• The 50-megawatt solar array met 85% of local auxiliary power demands during peak daylight hours.\n"
            "• Grid transmission losses decreased by 18%.\n"
            "• Facility operations conform to IEEE 1547 interconnection standards."
        )
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Faithful presentation falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)

    def test_presentation_invented_metric_rejected(self):
        output = "Slide 3: Financial Returns\n• The microgrid yielded $24M in annual electrical savings for the municipality."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertTrue(len(res["unverified_metrics"]) > 0)

    def test_presentation_invented_event_rejected(self):
        output = "HelioGrid completed the acquisition of Arizona Solar Systems to scale desert operations."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("acquisition", res["unsupported_events"])

    def test_presentation_unsupported_causal_rejected(self):
        output = "The photovoltaic microgrid installation guaranteed perpetual energy resilience across the entire state."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)

    # --- 5. VIDEO PACKAGE TESTS (using SOLAR_GRID_SOURCE) ---
    def test_video_package_source_faithful_grounded(self):
        output = (
            "Video Production Package: HelioGrid Mojave Desert Microgrid\n"
            "Video Objective: Inform stakeholders on facility launch and performance metrics.\n"
            "Full Voiceover Script:\n"
            "HelioGrid completed the installation of its smart photovoltaic microgrid at the Mojave Desert facility in August 2025. "
            "During peak daylight hours, the 50-megawatt solar array met 85% of local auxiliary power demands while reducing grid transmission losses by 18%. "
            "The facility utilizes lithium-iron-phosphate battery storage and conforms to IEEE 1547 interconnection standards.\n"
            "Storyboard Breakdown:\n"
            "Scene 1: Drone footage of Mojave Desert facility.\n"
            "On-Screen Text: HelioGrid smart photovoltaic microgrid installed August 2025.\n"
            "Scene 2: Graphic display of 50-megawatt array.\n"
            "On-Screen Text: Met 85% of auxiliary power demands with 18% reduction in transmission losses."
        )
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertTrue(res["is_grounded"], f"Faithful video package falsely ungrounded: {res}")
        self.assertEqual(len(res["unsupported_claims"]), 0)
        self.assertEqual(len(res["unverified_metrics"]), 0)

    def test_video_package_invented_metric_rejected(self):
        output = "Scene 2 On-Screen Text: Microgrid reduced total facility operating costs by 62%."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("62%", res["unverified_metrics"])

    def test_video_package_invented_event_rejected(self):
        output = "HelioGrid entered into an enterprise partnership with the Department of Defense to construct tactical microgrids."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertIn("partnership", res["unsupported_events"])

    def test_video_package_unsupported_benefit_rejected(self):
        output = "The solar microgrid deployment permanently solved climate disruption across the entire region."
        res = verify_factual_grounding(SOLAR_GRID_SOURCE, output)
        self.assertFalse(res["is_grounded"])
        self.assertGreaterEqual(len(res["unsupported_claims"]), 1)



class TestFeedbackAwareTargetedRecovery(unittest.TestCase):
    """
    Test suite for feedback-aware targeted recovery:
    Verifies that grounding failures trigger targeted recovery,
    recovery prompts contain explicit detected defects and previous drafts,
    clean outputs do not trigger recovery, and non-critical warnings do not cause spurious recoveries.
    """

    def test_recovery_prompt_contains_detected_issues(self):
        prompt = build_recovery_prompt(
            source_content=CYBERSHIELD_SOURCE,
            output_type="Executive Summary",
            target_audience="C-Suite & Executive Leadership",
            tone="Professional",
            language="English",
            detail_level="Detailed",
            validation_issues=[
                "Output contains unverified metric(s): $500M.",
                "Output contains unsupported event(s): acquisition."
            ],
            previous_output="CyberShield acquired a German robotics startup and raised $500M.",
            grounding_details={
                "unverified_metrics": ["$500M"],
                "unsupported_events": ["acquisition"],
                "unsupported_entities": ["German robotics startup"],
                "unsupported_claims": ["CyberShield acquired a German robotics startup and raised $500M."]
            }
        )
        # Verify detected defects are explicitly injected into the prompt
        self.assertIn("SPECIFIC DEFECTS & GROUNDING VIOLATIONS TO FIX:", prompt)
        self.assertIn("$500M", prompt)
        self.assertIn("acquisition", prompt)
        self.assertIn("German robotics startup", prompt)
        self.assertIn("UNVERIFIED METRIC(S) NOT IN SOURCE", prompt)
        self.assertIn("UNSUPPORTED EVENT(S) NOT IN SOURCE", prompt)
        self.assertIn("RECOVERY INSTRUCTIONS:", prompt)
        self.assertIn("ELIMINATE all unverified metrics", prompt)

    def test_recovery_prompt_includes_previous_draft(self):
        draft_text = "Project CyberShield reported 99.4% intrusion mitigation and acquired a Munich firm."
        prompt = build_recovery_prompt(
            source_content=CYBERSHIELD_SOURCE,
            output_type="Executive Summary",
            target_audience="Engineering & Technical Teams",
            tone="Professional",
            language="English",
            detail_level="Detailed",
            previous_output=draft_text,
            validation_issues=["Output contains unsupported event(s): acquisition."]
        )
        self.assertIn("PREVIOUS DRAFT (REJECTED DUE TO QUALITY / GROUNDING VIOLATIONS):", prompt)
        self.assertIn(draft_text, prompt)

    def test_recovery_prompt_handles_empty_previous_draft(self):
        prompt = build_recovery_prompt(
            source_content=CYBERSHIELD_SOURCE,
            output_type="Advisory",
            target_audience="General Audience",
            tone="Professional",
            language="English",
            detail_level="Brief",
            previous_output="",
            validation_issues=["Output is missing or empty."]
        )
        self.assertIn("PREVIOUS DRAFT: [Missing or empty output from initial generation]", prompt)

    def test_grounding_failure_triggers_recovery(self):
        # Case A: Unverified metric
        val_metric = {
            "valid": True,
            "severity": "warning",
            "issues": ["Output contains unverified metric(s): 95%."],
            "factual_grounding": {
                "is_grounded": False,
                "unverified_metrics": ["95%"],
                "unsupported_events": [],
                "unsupported_entities": [],
                "unsupported_claims": []
            }
        }
        self.assertTrue(should_trigger_recovery(val_metric))

        # Case B: Unsupported corporate event
        val_event = {
            "valid": True,
            "severity": "warning",
            "issues": ["Output contains unsupported event(s): acquisition."],
            "factual_grounding": {
                "is_grounded": False,
                "unverified_metrics": [],
                "unsupported_events": ["acquisition"],
                "unsupported_entities": [],
                "unsupported_claims": []
            }
        }
        self.assertTrue(should_trigger_recovery(val_event))

        # Case C: Unsupported entity
        val_entity = {
            "valid": True,
            "severity": "warning",
            "issues": ["Output contains unsupported entity/fact(s): Munich Robotics."],
            "factual_grounding": {
                "is_grounded": False,
                "unverified_metrics": [],
                "unsupported_events": [],
                "unsupported_entities": ["Munich Robotics"],
                "unsupported_claims": []
            }
        }
        self.assertTrue(should_trigger_recovery(val_entity))

        # Case D: Unsupported claims
        val_claims = {
            "valid": True,
            "severity": "warning",
            "issues": ["Output contains 1 claim(s) unsupported by source content."],
            "factual_grounding": {
                "is_grounded": False,
                "unverified_metrics": [],
                "unsupported_events": [],
                "unsupported_entities": [],
                "unsupported_claims": ["The system achieved complete planetary dominance."]
            }
        }
        self.assertTrue(should_trigger_recovery(val_claims))

    def test_structural_error_triggers_recovery(self):
        # Structural error (e.g. empty output or missing slide breakdown)
        val_structural = {
            "valid": False,
            "severity": "error",
            "issues": ["Presentation lacks slide-by-slide structure or speaker notes."],
            "factual_grounding": {"is_grounded": True}
        }
        self.assertTrue(should_trigger_recovery(val_structural))

    def test_clean_grounded_output_does_not_trigger_recovery(self):
        val_clean = {
            "valid": True,
            "severity": "none",
            "issues": [],
            "factual_grounding": {
                "is_grounded": True,
                "unverified_metrics": [],
                "unsupported_events": [],
                "unsupported_entities": [],
                "unsupported_claims": []
            }
        }
        self.assertFalse(should_trigger_recovery(val_clean))

    def test_non_critical_warning_does_not_trigger_recovery(self):
        # Configuration warning (e.g., detail level mismatch or minor formatting)
        val_warning = {
            "valid": True,
            "severity": "warning",
            "issues": ["Output length significantly exceeds requested 'Brief' detail level."],
            "factual_grounding": {
                "is_grounded": True,
                "unverified_metrics": [],
                "unsupported_events": [],
                "unsupported_entities": [],
                "unsupported_claims": []
            }
        }
        self.assertFalse(
            should_trigger_recovery(val_warning),
            "Non-critical configuration warning should NOT trigger recovery"
        )

    def test_validate_and_recover_outputs_calls_recovery_on_grounding_failure(self):
        # Initial ungrounded output with fabricated 95% metric
        initial_outputs = {
            "Executive Summary": (
                "Executive Overview:\n"
                "Project CyberShield automated detection reduced threat response times by 95%.\n"
                "Strategic Pillars:\n"
                "Real-time anomaly detection and continuous posture management.\n"
                "Key Takeaways:\n"
                "Received SOC2 Type II certification and ISO/IEC 27001 compliance."
            )
        }
        request = TransformRequest(
            source_content=CYBERSHIELD_SOURCE,
            output_types=["Executive Summary"]
        )

        # Mock model that returns a clean, fully grounded output upon recovery
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "Executive Overview:\n"
            "Project CyberShield automated detection reduced threat response times by 68%.\n"
            "Key Pillars:\n"
            "Real-time anomaly detection and continuous posture management.\n"
            "Key Takeaways:\n"
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards."
        )
        mock_model.generate_content.return_value = mock_response

        final_outputs, val_report = validate_and_recover_outputs(
            outputs=initial_outputs,
            request=request,
            model=mock_model,
            multimodal_parts=[]
        )

        # Verify targeted recovery was triggered and executed
        self.assertEqual(val_report["recovered_count"], 1)
        self.assertIn("Executive Summary", val_report["recovered_formats"])
        # Verify the mock model was called for targeted recovery
        mock_model.generate_content.assert_called_once()
        # Verify the prompt passed to the model was feedback-aware
        call_args = mock_model.generate_content.call_args[0][0]
        prompt_sent = call_args if isinstance(call_args, str) else call_args[0]
        self.assertIn("SPECIFIC DEFECTS & GROUNDING VIOLATIONS TO FIX:", prompt_sent)
        self.assertIn("95%", prompt_sent)

        # Verify output was updated with the recovered version
        self.assertIn("68%", final_outputs["Executive Summary"])
        # Verify recovered output is now grounded
        exec_val = val_report["per_output"]["Executive Summary"]
        self.assertTrue(exec_val["factual_grounding"]["is_grounded"])

    def test_validate_and_recover_outputs_skips_recovery_for_clean_outputs(self):
        # Initial clean output
        initial_outputs = {
            "Executive Summary": (
                "Executive Overview:\n"
                "Project CyberShield automated detection reduced threat response times by 68%.\n"
                "Key Pillars:\n"
                "Real-time anomaly detection and continuous posture management.\n"
                "Key Takeaways:\n"
                "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards."
            )
        }
        request = TransformRequest(
            source_content=CYBERSHIELD_SOURCE,
            output_types=["Executive Summary"]
        )
        mock_model = MagicMock()

        final_outputs, val_report = validate_and_recover_outputs(
            outputs=initial_outputs,
            request=request,
            model=mock_model,
            multimodal_parts=[]
        )

        # Clean output should NOT trigger recovery
        self.assertEqual(val_report["recovered_count"], 0)
        self.assertEqual(val_report["recovered_formats"], [])
        mock_model.generate_content.assert_not_called()


class TestTwitterFormatValidation(unittest.TestCase):
    """
    Test suite for Twitter/X Post format validation:
    Verifies valid outputs pass, overlong posts and segments are detected,
    missing/malformed hashtags are detected, invented metrics/events are flagged,
    and clean grounded outputs do not trigger unnecessary recovery.
    """

    def test_valid_source_faithful_twitter_output_passes(self):
        # Single tweet under 280 characters with hashtags and grounded facts
        output_single = (
            "Project CyberShield automated detection reduced threat response times by 68%, "
            "mitigating 99.4% of simulated intrusions during internal pilot testing. #CyberShield #ZeroTrust"
        )
        val_single = validate_output(
            output_type="Twitter/X Post",
            output_text=output_single,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val_single["valid"])
        self.assertEqual(len(val_single["issues"]), 0, f"Unexpected issues in valid tweet: {val_single['issues']}")
        self.assertTrue(val_single["factual_grounding"]["is_grounded"])

        # Thread with 2 segments under 280 characters each with hashtags
        output_thread = (
            "1/2: Project CyberShield automated detection reduced threat response times by 68% in Q1 2026 pilot tests.\n"
            "2/2: The framework mitigated 99.4% of simulated intrusions before lateral movement occurred. #CyberShield"
        )
        val_thread = validate_output(
            output_type="Twitter/X Post",
            output_text=output_thread,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val_thread["valid"])
        self.assertEqual(len(val_thread["issues"]), 0, f"Unexpected issues in valid thread: {val_thread['issues']}")
        self.assertTrue(val_thread["factual_grounding"]["is_grounded"])

    def test_overlong_single_twitter_output_detected(self):
        # Single unthreaded post exceeding 280 characters
        output_overlong = (
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026 to safeguard cloud "
            "infrastructure, identify zero-day vulnerabilities, and ensure zero-trust compliance across distributed "
            "multi-cloud environments. During internal pilot testing, automated detection reduced threat response "
            "times by 68%, mitigating 99.4% of simulated intrusions. #CyberShield"
        )
        self.assertGreater(len(output_overlong), 280)
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_overlong,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(any("exceeds 280-character" in issue for issue in val["issues"]))

    def test_overlong_thread_segment_detected(self):
        # Thread where second segment exceeds 280 characters
        long_body = "During internal pilot testing, automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral movement occurred across all environments. " * 2
        output_overlong_thread = (
            "1/2: CyberShield reduced response times by 68%. #CyberShield\n"
            f"2/2: {long_body} #ZeroTrust"
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_overlong_thread,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(any("exceeding the 280-character limit" in issue for issue in val["issues"]))

    def test_missing_hashtag_formatting_detected(self):
        # Output lacking any hashtag
        output_no_hashtag = (
            "Project CyberShield automated detection reduced threat response times by 68%, "
            "mitigating 99.4% of intrusions in pilot tests."
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_no_hashtag,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(any("missing required hashtags" in issue.lower() for issue in val["issues"]))

    def test_malformed_hashtag_formatting_detected(self):
        # Output with markdown header but no actual hashtags
        output_malformed = (
            "### Project CyberShield Update\n"
            "Automated detection reduced threat response times by 68% in pilot tests. Tag: #"
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_malformed,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(any("missing required hashtags" in issue.lower() for issue in val["issues"]))

    def test_invented_metric_still_detected_as_grounding_failure(self):
        # Twitter post with invented 99.9% metric
        output_invented_metric = (
            "Project CyberShield eliminated 99.9% of all corporate network intrusions. #CyberShield"
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_invented_metric,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertFalse(val["factual_grounding"]["is_grounded"])
        self.assertIn("99.9%", val["factual_grounding"]["unverified_metrics"])
        # Should trigger recovery because of critical grounding failure
        self.assertTrue(should_trigger_recovery(val))

    def test_invented_event_still_detected_as_grounding_failure(self):
        # Twitter post with invented corporate acquisition
        output_invented_event = (
            "Project CyberShield finalized the acquisition of a German security firm. #CyberShield"
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_invented_event,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertFalse(val["factual_grounding"]["is_grounded"])
        self.assertIn("acquisition", val["factual_grounding"]["unsupported_events"])
        # Should trigger recovery because of critical grounding failure
        self.assertTrue(should_trigger_recovery(val))

    def test_clean_grounded_twitter_output_does_not_trigger_unnecessary_recovery(self):
        # Clean, compliant Twitter post
        output_clean = (
            "Project CyberShield automated detection reduced threat response times by 68% in pilot tests. #CyberShield"
        )
        val = validate_output(
            output_type="Twitter/X Post",
            output_text=output_clean,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertEqual(len(val["issues"]), 0)
        self.assertFalse(should_trigger_recovery(val))


class TestFrenchAndGermanLanguageValidation(unittest.TestCase):
    """
    Test suite for French and German language validation in validate_output:
    Verifies valid French and German outputs pass without language warnings,
    and English leakage is correctly detected when French or German is requested.
    """

    def test_valid_french_output_passes(self):
        french_output = (
            "Résumé Exécutif:\n"
            "Le projet CyberShield est un cadre de cybersécurité pour protéger l'infrastructure infonuagique. "
            "La détection automatisée a réduit les temps de réponse de 68% pendant les tests pilotes. "
            "La plateforme a obtenu la certification SOC2 Type II et respecte les normes ISO/IEC 27001."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=french_output,
            source_content=CYBERSHIELD_SOURCE,
            language="French"
        )
        language_issues = [i for i in val["issues"] if "language" in i.lower() or "french" in i.lower()]
        self.assertEqual(len(language_issues), 0, f"Unexpected language issue in valid French output: {language_issues}")

    def test_english_leakage_in_french_output_detected(self):
        english_output = (
            "Executive Summary Overview:\n"
            "Project CyberShield automated detection reduced threat response times by 68%. "
            "The platform has received SOC2 Type II certification."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=english_output,
            source_content=CYBERSHIELD_SOURCE,
            language="French"
        )
        self.assertTrue(
            any("rather than requested language 'French'" in issue for issue in val["issues"]),
            f"Expected French language leakage warning, got issues: {val['issues']}"
        )

    def test_valid_german_output_passes(self):
        german_output = (
            "Zusammenfassung:\n"
            "Das Projekt CyberShield ist ein Sicherheitsframework zum Schutz der Cloud-Infrastruktur. "
            "Die automatisierte Erkennung reduzierte die Reaktionszeiten bei internen Pilottests um 68%. "
            "Die Plattform erfüllt die Normen von ISO/IEC 27001 und erhielt die SOC2-Zertifizierung."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=german_output,
            source_content=CYBERSHIELD_SOURCE,
            language="German"
        )
        language_issues = [i for i in val["issues"] if "language" in i.lower() or "german" in i.lower()]
        self.assertEqual(len(language_issues), 0, f"Unexpected language issue in valid German output: {language_issues}")

    def test_english_leakage_in_german_output_detected(self):
        english_output = (
            "Executive Summary Overview:\n"
            "Project CyberShield automated detection reduced threat response times by 68%. "
            "The platform has received SOC2 Type II certification."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=english_output,
            source_content=CYBERSHIELD_SOURCE,
            language="German"
        )
        self.assertTrue(
            any("rather than requested language 'German'" in issue for issue in val["issues"]),
            f"Expected German language leakage warning, got issues: {val['issues']}"
        )


class TestPresentationFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for Presentation format-specific validation in validate_output():
    - Valid 4-6 slide presentation with headers, bullets, and speaker notes
    - Too few slides (< 4 slides)
    - Generic text mentioning slides/speaker-notes rejected as false positive
    - Missing speaker notes / content
    - Clean valid presentation does not trigger recovery unnecessarily
    """

    def test_valid_presentation_output_passes(self):
        # Faithful 4-slide presentation matching specification
        valid_presentation = (
            "Slide 1: Title & Framework Overview\n"
            "• Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n"
            "• Safeguards cloud infrastructure across distributed multi-cloud environments.\n"
            "• Ensures zero-trust compliance and identifies zero-day vulnerabilities.\n"
            "• Speaker Notes: Welcome everyone. Today we are presenting Project CyberShield, initiated in Q1 2026.\n\n"
            "Slide 2: Pilot Testing Performance\n"
            "• Automated detection reduced threat response times by 68% during internal pilot testing.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement occurred.\n"
            "• Speaker Notes: Emphasize the measured 68% reduction in threat response times.\n\n"
            "Slide 3: Core Architectural Pillars\n"
            "• Key pillars include real-time anomaly detection and automated policy enforcement.\n"
            "• Features continuous posture management and seamless CI/CD security scanning.\n"
            "• Speaker Notes: Walk through the four architectural pillars safeguarding infrastructure.\n\n"
            "Slide 4: Compliance & Certifications\n"
            "• The platform has received SOC2 Type II certification.\n"
            "• Framework adheres to ISO/IEC 27001 standards.\n"
            "• Speaker Notes: Reassure stakeholders of full SOC2 Type II and ISO/IEC 27001 adherence."
        )
        val = validate_output(
            output_type="Presentation",
            output_text=valid_presentation,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid presentation marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid presentation: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_presentation_too_few_slides_detected(self):
        # Presentation with only 2 slides (specification requires 4-6 slides)
        two_slide_presentation = (
            "Slide 1: Title & Framework Overview\n"
            "• Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n"
            "• Speaker Notes: Present the framework overview.\n\n"
            "Slide 2: Pilot Testing Performance\n"
            "• Automated detection reduced threat response times by 68%.\n"
            "• Speaker Notes: Present measured pilot response times."
        )
        val = validate_output(
            output_type="Presentation",
            output_text=two_slide_presentation,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("only 2 slide" in issue.lower() or "4–6" in issue or "4-6" in issue for issue in val["issues"]),
            f"Expected slide count issue, got: {val['issues']}"
        )

    def test_generic_text_mentioning_slides_rejected(self):
        # Paragraph mentioning "slides" and "speaker notes" but lacking presentation slide markers
        generic_text = (
            "During the executive briefing, our team reviewed several slides describing the cloud cybersecurity project. "
            "The speaker notes outlined key findings and incident response times, but more cross-functional analysis is needed."
        )
        val = validate_output(
            output_type="Presentation",
            output_text=generic_text,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertFalse(val["valid"], "Generic text falsely passed as a valid presentation")
        self.assertEqual(val["severity"], "error")
        self.assertTrue(
            any("lacks slide-by-slide structure" in issue.lower() for issue in val["issues"]),
            f"Expected slide structure error, got: {val['issues']}"
        )
        self.assertTrue(should_trigger_recovery(val), "Structural failure should trigger recovery")

    def test_presentation_missing_speaker_notes_detected(self):
        # 4 slides with bullet points but no speaker notes
        no_notes_presentation = (
            "Slide 1: Title & Overview\n"
            "• Project CyberShield initiated in Q1 2026.\n\n"
            "Slide 2: Architecture\n"
            "• Automated policy enforcement and posture management.\n\n"
            "Slide 3: Performance\n"
            "• Threat response times reduced by 68%.\n\n"
            "Slide 4: Certifications\n"
            "• Platform received SOC2 Type II certification.\n"
        )
        val = validate_output(
            output_type="Presentation",
            output_text=no_notes_presentation,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("speaker notes" in issue.lower() for issue in val["issues"]),
            f"Expected missing speaker notes issue, got: {val['issues']}"
        )

    def test_presentation_missing_bullet_points_detected(self):
        # 4 slides with headers and speaker notes but no bullet points
        no_bullets_presentation = (
            "Slide 1: Title & Overview\n"
            "Speaker Notes: Welcome everyone to the presentation.\n\n"
            "Slide 2: Architecture\n"
            "Speaker Notes: Discuss policy enforcement.\n\n"
            "Slide 3: Performance\n"
            "Speaker Notes: Review response times.\n\n"
            "Slide 4: Certifications\n"
            "Speaker Notes: Conclude with certifications.\n"
        )
        val = validate_output(
            output_type="Presentation",
            output_text=no_bullets_presentation,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("bullet points" in issue.lower() or "slide content" in issue.lower() for issue in val["issues"]),
            f"Expected missing bullet points issue, got: {val['issues']}"
        )

    def test_clean_valid_presentation_does_not_trigger_unnecessary_recovery(self):
        # Clean grounded 4-slide presentation with speaker notes
        clean_presentation = (
            "Slide 1: Title & Framework Overview\n"
            "• Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n"
            "• Safeguards cloud infrastructure across distributed multi-cloud environments.\n"
            "• Speaker Notes: Welcome everyone to the presentation.\n\n"
            "Slide 2: Pilot Testing Performance\n"
            "• Automated detection reduced threat response times by 68% during internal pilot testing.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement occurred.\n"
            "• Speaker Notes: Detail the measured response time reduction.\n\n"
            "Slide 3: Core Architectural Pillars\n"
            "• Key pillars include real-time anomaly detection and automated policy enforcement.\n"
            "• Features continuous posture management and seamless CI/CD security scanning.\n"
            "• Speaker Notes: Explain the security pillars.\n\n"
            "Slide 4: Compliance & Certifications\n"
            "• The platform has received SOC2 Type II certification.\n"
            "• Framework adheres to ISO/IEC 27001 standards.\n"
            "• Speaker Notes: Conclude with certifications and open for questions."
        )
        val = validate_output(
            output_type="Presentation",
            output_text=clean_presentation,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in clean presentation: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid presentation should not trigger recovery")


class TestExecutiveSummaryFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for Executive Summary format-specific validation in validate_output():
    - Valid multi-section Executive Summary (>= 2 recognized structural categories)
    - Generic prose mentioning keywords rejected / flagged
    - Incomplete Executive Summary with only 1 structural category flagged
    - Executive Summary with Overview + Findings passes
    - Executive Summary with Recommendations + Takeaways passes
    - Clean valid Executive Summary does not trigger recovery unnecessarily
    """

    def test_valid_executive_summary_output_passes(self):
        # Valid Executive Summary with Overview, Findings/Impact, and Recommendations
        valid_summary = (
            "Executive Overview:\n"
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026 to "
            "safeguard cloud infrastructure across distributed multi-cloud environments.\n\n"
            "Key Findings & Measured Impact:\n"
            "During internal pilot testing, automated detection reduced threat response times by 68%, "
            "mitigating 99.4% of simulated intrusions before lateral movement occurred.\n\n"
            "Strategic Recommendations:\n"
            "Maintain continuous posture management and adhere to ISO/IEC 27001 standards."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=valid_summary,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid Executive Summary marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid Executive Summary: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_generic_text_mentioning_summary_rejected(self):
        # Running paragraph containing keywords without actual structural sections
        generic_text = "In summary, the project had an impact and several findings were discussed."
        val = validate_output(
            output_type="Executive Summary",
            output_text=generic_text,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks multi-section structure" in issue.lower() or "structural" in issue.lower() for issue in val["issues"]),
            f"Expected multi-section structure issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_executive_summary_missing_structural_sections_detected(self):
        # Only 1 structural category (Overview only)
        one_section_summary = (
            "Executive Overview:\n"
            "Project CyberShield was initiated in Q1 2026 to safeguard cloud infrastructure. "
            "Automated detection reduced threat response times by 68% during internal pilot testing."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=one_section_summary,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("only 1 structural component" in issue.lower() or "requires at least two" in issue.lower() for issue in val["issues"]),
            f"Expected missing structural section issue, got: {val['issues']}"
        )

    def test_executive_summary_with_overview_and_findings_passes(self):
        # Two valid categories: Overview/Context and Findings/Impact
        overview_findings = (
            "## Context & Background\n"
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n\n"
            "## Key Findings\n"
            "Automated detection reduced threat response times by 68% in pilot tests, mitigating 99.4% of intrusions."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=overview_findings,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_executive_summary_with_recommendations_and_takeaways_passes(self):
        # Two valid categories: Findings/Impact (Takeaways) and Action (Action Items)
        takeaways_actions = (
            "Key Takeaways:\n"
            "Automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions.\n\n"
            "Action Items:\n"
            "Maintain continuous posture management and enforce ISO/IEC 27001 standards."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=takeaways_actions,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_clean_valid_executive_summary_does_not_trigger_unnecessary_recovery(self):
        # Clean, grounded, structurally valid output
        clean_summary = (
            "Executive Overview:\n"
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n\n"
            "Key Findings:\n"
            "Automated detection reduced threat response times by 68% during pilot testing, mitigating 99.4% of intrusions.\n\n"
            "Recommended Actions:\n"
            "Maintain SOC2 Type II certification and adherence to ISO/IEC 27001 standards."
        )
        val = validate_output(
            output_type="Executive Summary",
            output_text=clean_summary,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid Executive Summary should not trigger recovery")


class TestAdvisoryFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for Advisory format-specific validation in validate_output():
    - Valid advisory with both Risk/Context and Directive/Guidance components passes
    - Generic prose mentioning keywords is flagged
    - Advisory with Risk/Context only is flagged as incomplete
    - Advisory with Directive/Guidance only is flagged as incomplete
    - Clean valid advisory does not trigger recovery unnecessarily
    """

    def test_valid_advisory_output_passes(self):
        # Valid advisory with both Risk/Context and Directive/Guidance, grounded in source
        valid_advisory = (
            "Context & Risk Analysis:\n"
            "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026 to "
            "safeguard cloud infrastructure across distributed multi-cloud environments. "
            "During internal pilot testing, automated detection reduced threat response times by 68%, "
            "mitigating 99.4% of simulated intrusions before lateral movement occurred.\n\n"
            "Mandatory Directives & Guidance:\n"
            "1. Enforce automated policy enforcement across CI/CD pipelines.\n"
            "2. Adhere to ISO/IEC 27001 standards and maintain SOC2 Type II compliance."
        )
        val = validate_output(
            output_type="Advisory",
            output_text=valid_advisory,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid Advisory marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid Advisory: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_generic_text_mentioning_advisory_keywords_flagged(self):
        # Generic running prose mentioning keywords without actual structural sections
        generic_prose = "In this update, the risk was evaluated, the impact was discussed, and several action items were considered."
        val = validate_output(
            output_type="Advisory",
            output_text=generic_prose,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks clear risk/context framing and directive/guidance structure" in issue.lower() or "structure" in issue.lower() for issue in val["issues"]),
            f"Expected structure issue for generic prose, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_advisory_risk_context_only_flagged(self):
        # Contains Risk/Context only, missing Directive/Guidance
        risk_only = (
            "Context & Risk Analysis:\n"
            "Project CyberShield safeguards cloud infrastructure against zero-day vulnerabilities. "
            "During pilot testing, automated detection reduced threat response times by 68%."
        )
        val = validate_output(
            output_type="Advisory",
            output_text=risk_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks actionable directives or guidance" in issue.lower() or "directives" in issue.lower() for issue in val["issues"]),
            f"Expected missing directives issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_advisory_directive_guidance_only_flagged(self):
        # Contains Directive/Guidance only, missing Risk/Context
        directive_only = (
            "Mandatory Directives:\n"
            "1. Enforce automated policy enforcement across distributed multi-cloud environments.\n"
            "2. Adhere to ISO/IEC 27001 standards and verify SOC2 Type II compliance."
        )
        val = validate_output(
            output_type="Advisory",
            output_text=directive_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks risk analysis or context framing" in issue.lower() or "risk" in issue.lower() for issue in val["issues"]),
            f"Expected missing risk framing issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_clean_valid_advisory_does_not_trigger_unnecessary_recovery(self):
        # Clean grounded advisory with both components
        clean_advisory = (
            "Threat Context & Risk Impact:\n"
            "Project CyberShield was initiated in Q1 2026 to safeguard cloud infrastructure. "
            "Automated detection reduced threat response times by 68% during internal pilot testing.\n\n"
            "Recommended Guidance & Action Required:\n"
            "1. Implement continuous posture management and automated policy enforcement.\n"
            "2. Ensure adherence to ISO/IEC 27001 standards."
        )
        val = validate_output(
            output_type="Advisory",
            output_text=clean_advisory,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in clean advisory: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid Advisory should not trigger recovery")


class TestInfographicFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for Infographic format-specific validation in validate_output():
    - Valid infographic blueprint with both Visual/Layout and Data/Content components passes
    - Generic prose mentioning keywords is flagged
    - Infographic with Visual/Layout only is flagged as incomplete
    - Infographic with Data/Metrics only is flagged as incomplete
    - Clean valid infographic does not trigger recovery unnecessarily
    """

    def test_valid_infographic_blueprint_passes(self):
        # Valid infographic blueprint with visual recommendations and data callouts
        valid_infographic = (
            "Infographic Blueprint: Project CyberShield Framework\n\n"
            "Core Key Message:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments.\n\n"
            "Key Data & Metric Callouts:\n"
            "• Pilot Threat Response: 68% reduction in threat response times.\n"
            "• Intrusion Mitigation: 99.4% of simulated intrusions mitigated before lateral movement.\n\n"
            "Sectional Narrative Flow:\n"
            "• Section 1: Overview and zero-trust framework objectives.\n"
            "• Section 2: Real-time anomaly detection and automated policy enforcement.\n"
            "• Section 3: SOC2 Type II certification and ISO/IEC 27001 compliance.\n\n"
            "Layout & Visual Recommendations:\n"
            "• Visual Layout: Top banner header with metric cards and narrative flow.\n"
            "• Recommended Color Palette: Modern dark slate with indigo accents.\n"
            "• Icon Suggestions: Shield icon for zero-trust compliance, checkmark for certifications."
        )
        val = validate_output(
            output_type="Infographic",
            output_text=valid_infographic,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid Infographic marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid Infographic: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_generic_prose_infographic_keywords_flagged(self):
        # Generic running prose mentioning keywords without actual structural sections
        generic_prose = "In this section, the visual design illustrates key metrics for the infographic and highlights overall performance."
        val = validate_output(
            output_type="Infographic",
            output_text=generic_prose,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks visual/layout recommendations and sectional data" in issue.lower() or "visual" in issue.lower() for issue in val["issues"]),
            f"Expected structure issue for generic prose, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_infographic_layout_visual_only_flagged(self):
        # Contains Layout/Visual recommendations only, missing sectional data/metric callouts
        visual_only = (
            "Layout & Visual Recommendations:\n"
            "• Visual Layout: Header banner with 3-column split layout and narrative footer.\n"
            "• Recommended Color Palette: Dark slate with cobalt blue accents.\n"
            "• Icon Suggestions: Shield icon for cybersecurity framework."
        )
        val = validate_output(
            output_type="Infographic",
            output_text=visual_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks sectional stat/metric callouts" in issue.lower() or "data" in issue.lower() for issue in val["issues"]),
            f"Expected missing data/metric callout issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_infographic_metrics_data_only_flagged(self):
        # Contains Sectional stat/metric callouts only, missing layout/visual recommendations
        data_only = (
            "Key Data & Metric Callouts:\n"
            "• Pilot Performance: 68% reduction in threat response times.\n"
            "• Mitigation Rate: 99.4% of simulated intrusions prevented before lateral movement.\n\n"
            "Sectional Breakdown:\n"
            "• Section 1: Pilot testing metrics.\n"
            "• Section 2: Framework architecture."
        )
        val = validate_output(
            output_type="Infographic",
            output_text=data_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks layout or visual design recommendations" in issue.lower() or "visual" in issue.lower() for issue in val["issues"]),
            f"Expected missing visual recommendations issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_clean_valid_infographic_does_not_trigger_unnecessary_recovery(self):
        # Clean grounded infographic blueprint with both components
        clean_infographic = (
            "Infographic Blueprint: Project CyberShield Framework\n\n"
            "Core Key Message:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments.\n\n"
            "Key Data & Metric Callouts:\n"
            "• Pilot Threat Response: 68% reduction in threat response times.\n"
            "• Intrusion Mitigation: 99.4% of simulated intrusions mitigated before lateral movement.\n\n"
            "Sectional Narrative Flow:\n"
            "• Section 1: Overview and zero-trust framework objectives.\n"
            "• Section 2: Real-time anomaly detection and automated policy enforcement.\n"
            "• Section 3: SOC2 Type II certification and ISO/IEC 27001 compliance.\n\n"
            "Layout & Visual Recommendations:\n"
            "• Visual Layout: Top banner header with metric cards and narrative flow.\n"
            "• Recommended Color Palette: Modern dark slate with indigo accents.\n"
            "• Icon Suggestions: Shield icon for zero-trust compliance, checkmark for certifications."
        )
        val = validate_output(
            output_type="Infographic",
            output_text=clean_infographic,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in clean infographic: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid Infographic should not trigger recovery")


class TestVideoPackageFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for Video Package format-specific validation in validate_output():
    - Valid video package with both scenes and voiceover script passes
    - Generic prose mentioning keywords is flagged
    - Video package with scenes/storyboard only is flagged as incomplete
    - Video package with voiceover only is flagged as incomplete
    - Clean valid video package does not trigger recovery unnecessarily
    """

    def test_valid_video_package_passes(self):
        # Valid video package with full voiceover and storyboard scene breakdown
        valid_video = (
            "Video Production Package: Project CyberShield Framework\n"
            "Video Objective: Inform stakeholders on enterprise framework capabilities and metrics.\n"
            "Full Voiceover Script:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments. "
            "During internal pilot testing, automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral movement. "
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.\n"
            "Storyboard Breakdown:\n"
            "Scene 1: Motion graphics of multi-cloud environments.\n"
            "On-Screen Text: Project CyberShield zero-trust architecture.\n"
            "Scene 2: Graphic display of pilot metrics.\n"
            "On-Screen Text: 68% reduction in threat response times and 99.4% intrusion mitigation."
        )
        val = validate_output(
            output_type="Video Package",
            output_text=valid_video,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid Video Package marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid Video Package: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_generic_prose_video_keywords_flagged(self):
        # Generic running prose mentioning keywords without actual structural sections
        generic_prose = "In this video package, the scene is set in an office and the narration explains the core concepts and storyboard."
        val = validate_output(
            output_type="Video Package",
            output_text=generic_prose,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks scene-by-scene storyboard structure and voiceover narration script" in issue.lower() or "storyboard" in issue.lower() for issue in val["issues"]),
            f"Expected structure issue for generic prose, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_video_package_scenes_only_flagged(self):
        # Contains Scene breakdown / Storyboard only, missing voiceover script or audio dialogue
        scenes_only = (
            "Storyboard Breakdown:\n"
            "Scene 1: Drone footage over multi-cloud environments.\n"
            "Visual Description / Action: Animated infrastructure map demonstrating zero-trust coverage.\n"
            "On-Screen Text: Project CyberShield Architecture.\n"
            "Scene 2: Graphic display of pilot metrics.\n"
            "On-Screen Text: 68% reduction in threat response times."
        )
        val = validate_output(
            output_type="Video Package",
            output_text=scenes_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks voiceover narration script or audio dialogue" in issue.lower() or "voiceover" in issue.lower() for issue in val["issues"]),
            f"Expected missing voiceover script issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_video_package_voiceover_only_flagged(self):
        # Contains Voiceover script only, missing scene-by-scene storyboard or visual cues
        voiceover_only = (
            "Full Voiceover Script:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments. "
            "During internal pilot testing, automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral movement. "
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards."
        )
        val = validate_output(
            output_type="Video Package",
            output_text=voiceover_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("lacks scene-by-scene storyboard breakdown or visual cues" in issue.lower() or "storyboard" in issue.lower() for issue in val["issues"]),
            f"Expected missing storyboard breakdown issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_clean_valid_video_package_does_not_trigger_unnecessary_recovery(self):
        # Clean grounded video package with both components
        clean_video = (
            "Video Production Package: Project CyberShield Framework\n"
            "Video Objective: Inform stakeholders on enterprise framework capabilities and metrics.\n"
            "Full Voiceover Script:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments. "
            "During internal pilot testing, automated detection reduced threat response times by 68%, mitigating 99.4% of simulated intrusions before lateral movement. "
            "The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.\n"
            "Storyboard Breakdown:\n"
            "Scene 1: Motion graphics of multi-cloud environments.\n"
            "On-Screen Text: Project CyberShield zero-trust architecture.\n"
            "Scene 2: Graphic display of pilot metrics.\n"
            "On-Screen Text: 68% reduction in threat response times and 99.4% intrusion mitigation."
        )
        val = validate_output(
            output_type="Video Package",
            output_text=clean_video,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in clean video package: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid Video Package should not trigger recovery")


class TestLinkedInPostFormatValidation(unittest.TestCase):
    """
    Dedicated test suite for LinkedIn Post format-specific validation in validate_output():
    1. Valid structured LinkedIn post passes.
    2. Generic prose containing '#' is flagged.
    3. Hook-only post is flagged.
    4. Body/takeaways without hook or CTA is flagged.
    5. CTA-only post is flagged.
    6. Post without hashtags is flagged.
    7. Fully valid grounded LinkedIn post does not trigger unnecessary recovery.
    """

    def test_valid_structured_linkedin_post_passes(self):
        # Valid post with Hook, Body/Takeaways, CTA, and Hashtags
        valid_post = (
            "🛡️ Enterprise Cybersecurity Update:\n\n"
            "During internal pilot testing of Project CyberShield, automated detection reduced threat response times by 68% "
            "and blocked 99.4% of simulated intrusions before lateral movement!\n\n"
            "Key Takeaways:\n"
            "• Automated detection reduced threat response times by 68%.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement.\n"
            "• The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.\n\n"
            "What is your organization doing to advance zero-trust security? Share your thoughts below!\n\n"
            "#CyberSecurity #CloudSecurity #ZeroTrust"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=valid_post,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"], f"Valid LinkedIn Post marked invalid: {val}")
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in valid LinkedIn Post: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])

    def test_generic_prose_containing_hashtag_flagged(self):
        # Generic running prose mentioning keywords with a hashtag
        generic_prose = "In this post, the hook explains how cybersecurity is important, the takeaway is to use strong passwords, and the call to action is to stay safe #CyberSecurity"
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=generic_prose,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("missing structural components" in issue.lower() or "lacks required structure" in issue.lower() for issue in val["issues"]),
            f"Expected structural issue for generic prose, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_hook_only_post_flagged(self):
        # Has hook and hashtags, but lacks structured body/takeaways and CTA
        hook_only = (
            "🛡️ Enterprise Cybersecurity Update:\n"
            "Project CyberShield safeguards cloud infrastructure across distributed multi-cloud environments.\n\n"
            "#CyberSecurity #ZeroTrust"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=hook_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("body" in issue.lower() or "cta" in issue.lower() or "call-to-action" in issue.lower() for issue in val["issues"]),
            f"Expected missing body/CTA issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_body_takeaways_without_hook_or_cta_flagged(self):
        # Has body/takeaways and hashtags, but lacks hook and CTA
        body_only = (
            "Key Takeaways:\n"
            "• Reduced threat response times by 68%.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement.\n\n"
            "#CyberSecurity #ZeroTrust"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=body_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("opening hook" in issue.lower() or "call-to-action" in issue.lower() or "cta" in issue.lower() for issue in val["issues"]),
            f"Expected missing hook/CTA issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_cta_only_post_flagged(self):
        # Has CTA and hashtags, but lacks hook and body
        cta_only = (
            "What is your organization doing to advance zero-trust security? Share your thoughts below!\n\n"
            "#CyberSecurity #ZeroTrust"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=cta_only,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("opening hook" in issue.lower() or "body" in issue.lower() or "takeaways" in issue.lower() for issue in val["issues"]),
            f"Expected missing hook/body issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_post_without_hashtags_flagged(self):
        # Has hook, body, and CTA, but lacks hashtags
        no_hashtags = (
            "🛡️ Enterprise Cybersecurity Update:\n\n"
            "Key Takeaways:\n"
            "• Automated detection reduced threat response times by 68%.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement.\n\n"
            "What is your organization doing to advance zero-trust security? Share your thoughts below!"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=no_hashtags,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(
            any("missing hashtags" in issue.lower() for issue in val["issues"]),
            f"Expected missing hashtags issue, got: {val['issues']}"
        )
        self.assertEqual(val["severity"], "warning")

    def test_fully_valid_grounded_linkedin_post_does_not_trigger_unnecessary_recovery(self):
        # Fully valid grounded post
        valid_post = (
            "🛡️ Enterprise Cybersecurity Update:\n\n"
            "During internal pilot testing of Project CyberShield, automated detection reduced threat response times by 68% "
            "and blocked 99.4% of simulated intrusions before lateral movement!\n\n"
            "Key Takeaways:\n"
            "• Automated detection reduced threat response times by 68%.\n"
            "• Mitigated 99.4% of simulated intrusions before lateral movement.\n"
            "• The platform has received SOC2 Type II certification and adheres to ISO/IEC 27001 standards.\n\n"
            "What is your organization doing to advance zero-trust security? Share your thoughts below!\n\n"
            "#CyberSecurity #CloudSecurity #ZeroTrust"
        )
        val = validate_output(
            output_type="LinkedIn Post",
            output_text=valid_post,
            source_content=CYBERSHIELD_SOURCE
        )
        self.assertTrue(val["valid"])
        self.assertEqual(val["severity"], "none")
        self.assertEqual(len(val["issues"]), 0, f"Unexpected issues in clean LinkedIn Post: {val['issues']}")
        self.assertTrue(val["factual_grounding"]["is_grounded"])
        self.assertFalse(should_trigger_recovery(val), "Clean valid LinkedIn Post should not trigger recovery")


class TestCanonicalContentModel(unittest.TestCase):
    """
    Test suite for the Canonical Content Model (intermediate representation).
    Validates deterministic extraction, metrics preservation, entity/fact preservation,
    optional/empty fields handling, and compatibility with the /transform and /refine flows.
    """

    def test_canonical_model_creation_from_normal_source(self):
        """Verifies canonical model creation from standard CyberShield source text."""
        model = build_canonical_content_model(
            source_text=CYBERSHIELD_SOURCE,
            source_reference="cybershield_whitepaper.pdf"
        )
        self.assertIsInstance(model, CanonicalContentModel)
        self.assertEqual(model.source_reference, "cybershield_whitepaper.pdf")
        self.assertEqual(model.source_text, CYBERSHIELD_SOURCE)

        # Entities
        self.assertTrue(any("CyberShield" in e for e in model.entities), f"Entities: {model.entities}")

        # Metrics
        self.assertIn("68%", model.metrics)
        self.assertIn("99.4%", model.metrics)

        # Dates / Timeline
        self.assertTrue(any("Q1 2026" in d or "2026" in d for d in model.dates), f"Dates: {model.dates}")

        # Events
        self.assertTrue(any("launch" in ev.lower() or "initiat" in ev.lower() for ev in model.events), f"Events: {model.events}")
        self.assertTrue(any("certif" in ev.lower() for ev in model.events), f"Events: {model.events}")

        # Standards and Certifications
        self.assertTrue(any("SOC2" in s for s in model.standards_and_certifications), f"Standards: {model.standards_and_certifications}")
        self.assertTrue(any("27001" in s for s in model.standards_and_certifications), f"Standards: {model.standards_and_certifications}")

        # Substantive Claims
        self.assertGreaterEqual(len(model.claims), 3)

        # Risks & Impacts
        self.assertTrue(any("threat" in r.lower() or "vulnerabilit" in r.lower() for r in model.risks_and_impacts), f"Risks: {model.risks_and_impacts}")

        # Key Messages
        self.assertGreaterEqual(len(model.key_messages), 1)

        # Terminology
        self.assertTrue(len(model.terminology) > 0, f"Terminology: {model.terminology}")

        # Canonical context string representation
        ctx = model.to_canonical_context()
        self.assertIn("Source Reference: cybershield_whitepaper.pdf", ctx)
        self.assertIn("68%", ctx)
        self.assertIn("SOC2", ctx)

    def test_metrics_extraction_and_preservation(self):
        """Verifies exact extraction and preservation of percentages, currencies, multipliers, and units."""
        text = (
            "In fiscal year 2025, Acme Cloud generated $42.5 million in revenue (up 3.8x year-over-year) "
            "with 99.95% availability across 1,200 server nodes, achieving average latency of 14ms."
        )
        model = build_canonical_content_model(text, source_reference="acme_q4.txt")

        # Percentages
        self.assertIn("99.95%", model.metrics)
        # Currency
        self.assertTrue(any("$42.5 million" in m or "$42.5" in m for m in model.metrics), f"Metrics: {model.metrics}")
        # Multiplier
        self.assertTrue(any("3.8x" in m.lower() for m in model.metrics), f"Metrics: {model.metrics}")
        # Rate / latency
        self.assertTrue(any("14ms" in m.lower() for m in model.metrics), f"Metrics: {model.metrics}")
        # Quantity with units
        self.assertTrue(any("1,200 server nodes" in m.lower() or "server nodes" in m.lower() for m in model.metrics), f"Metrics: {model.metrics}")

    def test_entities_and_facts_preservation(self):
        """Verifies named entities, compound enterprise entities, and factual events are preserved."""
        text = (
            "Munich-based German cybersecurity firm SecuFlow announced a major partnership with Apex Systems in 2026. "
            "The company successfully completed its deployment across European enterprise networks."
        )
        model = build_canonical_content_model(text)

        # Entities
        self.assertTrue(any("SecuFlow" in e or "Apex Systems" in e or "cybersecurity firm" in e.lower() for e in model.entities), f"Entities: {model.entities}")

        # Events
        self.assertTrue(any("partnership" in ev.lower() for ev in model.events), f"Events: {model.events}")
        self.assertTrue(any("deployment" in ev.lower() for ev in model.events), f"Events: {model.events}")

        # Claims preservation
        self.assertGreaterEqual(len(model.claims), 2)
        self.assertTrue(any("SecuFlow" in c for c in model.claims))

    def test_empty_and_optional_fields(self):
        """Verifies that empty sources or sources without metrics/dates do not force fields."""
        # Empty string
        empty_model = build_canonical_content_model("")
        self.assertEqual(empty_model.source_text, "")
        self.assertEqual(empty_model.entities, [])
        self.assertEqual(empty_model.claims, [])
        self.assertEqual(empty_model.metrics, [])
        self.assertEqual(empty_model.dates, [])
        self.assertEqual(empty_model.events, [])
        self.assertEqual(empty_model.key_messages, [])
        self.assertEqual(empty_model.risks_and_impacts, [])
        self.assertEqual(empty_model.standards_and_certifications, [])
        self.assertEqual(empty_model.terminology, [])
        self.assertEqual(empty_model.to_canonical_context(), "")

        # Whitespace
        whitespace_model = build_canonical_content_model("   \n\t   ")
        self.assertEqual(whitespace_model.metrics, [])
        self.assertEqual(whitespace_model.claims, [])

        # Narrative without metrics, dates, or certifications
        narrative = "The engineering team met to review code quality and discuss internal workflow improvements."
        narrative_model = build_canonical_content_model(narrative)
        self.assertEqual(narrative_model.metrics, [], "Should not force metrics when none exist")
        self.assertEqual(narrative_model.dates, [], "Should not force dates when none exist")
        self.assertEqual(narrative_model.standards_and_certifications, [], "Should not force standards when none exist")
        self.assertGreaterEqual(len(narrative_model.claims), 1)

    def test_compatibility_with_transform_flow(self):
        """Verifies that mock_transform_content embeds CanonicalContentModel seamlessly without regression."""
        req = TransformRequest(
            source_content=CYBERSHIELD_SOURCE,
            output_types=["Executive Summary", "LinkedIn Post"],
            target_audience="C-Suite Executives",
            tone="Professional",
            document_name="cybershield_doc.txt"
        )
        res = mock_transform_content(req)

        # Existing response structure remains identical
        self.assertEqual(res.status, "success")
        self.assertIn("Executive Summary", res.outputs)
        self.assertIn("LinkedIn Post", res.outputs)
        self.assertIn("provenance", res.metadata)
        self.assertIn("Executive Summary", res.provenance)

        # Canonical Content Model is present and fully structured
        self.assertIsNotNone(res.canonical_content)
        self.assertIsInstance(res.canonical_content, CanonicalContentModel)
        self.assertEqual(res.canonical_content.source_reference, "cybershield_doc.txt")
        self.assertIn("68%", res.canonical_content.metrics)

        # Metadata dictionary includes canonical_content for backward-compatible clients
        self.assertIn("canonical_content", res.metadata)
        self.assertIsInstance(res.metadata["canonical_content"], dict)
        self.assertEqual(res.metadata["canonical_content"]["source_reference"], "cybershield_doc.txt")
        self.assertIn("68%", res.metadata["canonical_content"]["metrics"])

    def test_compatibility_with_refine_flow(self):
        """Verifies that mock_refine_content embeds CanonicalContentModel seamlessly."""
        req = RefineRequest(
            source_content=CYBERSHIELD_SOURCE,
            output_type="LinkedIn Post",
            current_output="[MOCK GENERATION - LINKEDIN POST]\nInitial text.",
            refinement_instruction="Make the hook more impactful and highlight SOC2 compliance."
        )
        res = mock_refine_content(req)

        self.assertEqual(res.status, "success")
        self.assertEqual(res.output_type, "LinkedIn Post")
        self.assertIsNotNone(res.canonical_content)
        self.assertIsInstance(res.canonical_content, CanonicalContentModel)
        self.assertIn("canonical_content", res.metadata)
        self.assertIn("68%", res.canonical_content.metrics)


class TestCrossFormatConsistencyAndQualityGate(unittest.TestCase):
    """
    Dedicated test suite for:
    1. Cross-format consistency validation (metrics, percentages, dates, entities, standards)
    2. Claim-level provenance (Source fact -> Canonical fact -> Generated claim -> Status)
    3. Deterministic explainable quality and confidence scoring
    4. Final Quality Gate evaluation and pipeline integration
    5. Compatibility with targeted recovery, /transform, and /refine
    """

    def setUp(self):
        self.source = CYBERSHIELD_SOURCE
        self.canonical_model = build_canonical_content_model(self.source, "cybershield_source.txt")

    def test_matching_metrics_across_formats_passes(self):
        """Matching canonical metrics (68%) across multiple generated formats -> PASS."""
        outputs = {
            "LinkedIn Post": "Automated detection reduced threat response times by 68% in Q1 2026. #CyberSecurity",
            "Twitter/X Post": "Threat response times reduced by 68% with automated detection! 🧵 1/2",
            "Presentation": "Slide 1: Key Metric - Threat response times reduced by 68% across all environments.",
            "Video Script": "Scene 1: Threat response times were cut by 68%."
        }
        report = validate_cross_format_consistency(outputs, self.canonical_model)
        self.assertTrue(report["consistent"], f"Expected consistent report, got: {report}")
        self.assertEqual(len(report["contradictions"]), 0)
        self.assertEqual(report["overall_consistency_score"], 1.0)
        for ot in outputs:
            self.assertEqual(report["format_consistency_scores"][ot], 1.0)

    def test_mismatched_metric_detected_as_contradiction(self):
        """Mismatched metric (65% instead of 68%) -> Contradiction flagged with expected vs observed."""
        outputs = {
            "LinkedIn Post": "Threat response reduced by 68% with automated detection.",
            "Twitter/X Post": "Threat response reduced by 68%.",
            "Presentation": "Threat response reduced by 68%.",
            "Video Script": "Threat response reduced by 65% across multi-cloud infrastructure."  # Contradiction!
        }
        report = validate_cross_format_consistency(outputs, self.canonical_model)
        self.assertFalse(report["consistent"])
        self.assertGreaterEqual(report["contradiction_count"], 1)

        metric_contras = [c for c in report["contradictions"] if c["element_type"] == "metric"]
        self.assertEqual(len(metric_contras), 1)
        contra = metric_contras[0]
        self.assertEqual(contra["observed_value"], "65%")
        self.assertEqual(contra["expected_value"], "68%")
        self.assertEqual(contra["affected_format"], "Video Script")
        self.assertEqual(contra["severity"], "error")
        self.assertEqual(contra["source_reference"], "cybershield_source.txt")
        self.assertLess(report["format_consistency_scores"]["Video Script"], 1.0)

    def test_mismatched_date_detected_as_contradiction(self):
        """Mismatched quarter/date (Q3 2025 or 2024 instead of Q1 2026) -> Contradiction flagged."""
        outputs = {
            "Executive Summary": "Project CyberShield was initiated in Q3 2025 to safeguard infrastructure.",
            "LinkedIn Post": "Initiated in Q1 2026 to safeguard cloud infrastructure."
        }
        report = validate_cross_format_consistency(outputs, self.canonical_model)
        self.assertFalse(report["consistent"])
        date_contras = [c for c in report["contradictions"] if c["element_type"] == "date"]
        self.assertGreaterEqual(len(date_contras), 1)
        dc = date_contras[0]
        self.assertEqual(dc["affected_format"], "Executive Summary")
        self.assertIn("2025", dc["observed_value"])
        self.assertEqual(dc["expected_value"], "Q1 2026")
        self.assertEqual(dc["severity"], "error")

    def test_mismatched_standard_and_entity_detected(self):
        """Mismatched standard or unsupported entity -> Contradiction flagged."""
        # Test standard mismatch: "SOC 1" instead of "SOC2 Type II"
        outputs = {
            "Advisory": "Adheres to SOC 1 Type I certification and ISO/IEC 27001 standards."
        }
        report = validate_cross_format_consistency(outputs, self.canonical_model)
        std_contras = [c for c in report["contradictions"] if c["element_type"] == "standard"]
        self.assertGreaterEqual(len(std_contras), 1)
        self.assertIn("SOC 1", std_contras[0]["observed_value"])
        self.assertEqual(std_contras[0]["affected_format"], "Advisory")
        self.assertEqual(std_contras[0]["severity"], "error")

        # Test unsupported entity passed via validation_results
        val_results = {
            "LinkedIn Post": {
                "valid": True,
                "severity": "none",
                "factual_grounding": {
                    "is_grounded": False,
                    "unsupported_entities": ["Acme Corp Global"],
                    "unverified_metrics": [],
                    "unsupported_events": [],
                    "unsupported_claims": ["Acme Corp Global acquired CyberShield"]
                }
            }
        }
        report2 = validate_cross_format_consistency(
            {"LinkedIn Post": "Acme Corp Global acquired CyberShield in Q1 2026."},
            self.canonical_model,
            validation_results=val_results
        )
        entity_contras = [c for c in report2["contradictions"] if c["element_type"] == "entity"]
        self.assertEqual(len(entity_contras), 1)
        self.assertEqual(entity_contras[0]["observed_value"], "Acme Corp Global")
        self.assertEqual(entity_contras[0]["affected_format"], "LinkedIn Post")

    def test_claim_level_provenance_structure_and_status(self):
        """Verifies claim-level provenance mapping: Source fact -> Canonical fact -> Claim -> Status."""
        text = (
            "Project CyberShield is an enterprise framework initiated in Q1 2026. "
            "Automated detection reduced threat response times by 68%. "
            "We also introduced ungrounded blockchain ledgers."
        )
        val_result = {
            "factual_grounding": {
                "is_grounded": False,
                "unsupported_claims": ["We also introduced ungrounded blockchain ledgers."],
                "unverified_metrics": []
            }
        }
        claims_prov = build_claim_level_provenance(
            output_type="LinkedIn Post",
            output_text=text,
            canonical_model=self.canonical_model,
            validation_result=val_result
        )
        self.assertGreaterEqual(len(claims_prov), 2)
        for record in claims_prov:
            self.assertIn("claim", record)
            self.assertIn("canonical_fact", record)
            self.assertIn("source_reference", record)
            self.assertIn("output_format", record)
            self.assertIn("status", record)
            self.assertEqual(record["output_format"], "LinkedIn Post")
            self.assertEqual(record["source_reference"], "cybershield_source.txt")

        # Check statuses
        verified_claims = [r for r in claims_prov if r["status"] == "verified"]
        unsupported_claims = [r for r in claims_prov if r["status"] == "unsupported"]
        self.assertGreaterEqual(len(verified_claims), 1)
        self.assertGreaterEqual(len(unsupported_claims), 1)

    def test_deterministic_quality_score_weights_and_calculation(self):
        """Verifies deterministic explainable quality score with exact documented weights."""
        clean_val = {
            "valid": True,
            "severity": "none",
            "issues": [],
            "factual_grounding": {
                "is_grounded": True,
                "claim_grounding_score": 1.0,
                "unverified_metrics": [],
                "unsupported_events": [],
                "unsupported_entities": []
            }
        }
        # Perfect score when validation is clean and consistency is 1.0
        score = calculate_quality_score(clean_val, consistency_score=1.0, contradiction_count=0)
        self.assertEqual(score["overall_score"], 1.0)
        self.assertEqual(score["grounding"], 1.0)
        self.assertEqual(score["structure"], 1.0)
        self.assertEqual(score["consistency"], 1.0)
        self.assertEqual(score["compliance"], 1.0)
        self.assertEqual(score["weights"]["grounding"], 0.35)
        self.assertEqual(score["weights"]["structure"], 0.25)
        self.assertEqual(score["weights"]["consistency"], 0.25)
        self.assertEqual(score["weights"]["compliance"], 0.15)

        # Degraded score when unverified metrics and contradictions exist
        degraded_val = {
            "valid": False,
            "severity": "error",
            "issues": ["Structural failure: Missing required section."],
            "factual_grounding": {
                "is_grounded": False,
                "claim_grounding_score": 0.5,
                "unverified_metrics": ["999%"],
                "unsupported_events": [],
                "unsupported_entities": []
            }
        }
        degraded_score = calculate_quality_score(degraded_val, consistency_score=0.70, contradiction_count=1)
        self.assertLess(degraded_score["overall_score"], 0.70)
        self.assertLess(degraded_score["grounding"], 1.0)
        self.assertLess(degraded_score["structure"], 1.0)
        self.assertLess(degraded_score["consistency"], 1.0)

    def test_quality_gate_pass_and_fail(self):
        """Verifies Quality Gate evaluation: PASS when threshold met without errors, FAIL otherwise."""
        # PASS scenario
        quality_scores = {
            "LinkedIn Post": {"overall_score": 0.95},
            "Executive Summary": {"overall_score": 0.92}
        }
        consistency_clean = {"contradictions": []}
        gate_result = evaluate_quality_gate(quality_scores, consistency_clean, threshold=0.80)
        self.assertTrue(gate_result["gate_passed"])
        self.assertEqual(gate_result["failing_formats"], [])
        self.assertGreaterEqual(gate_result["overall_quality_score"], 0.80)

        # FAIL scenario due to low score
        quality_scores_low = {
            "LinkedIn Post": {"overall_score": 0.95},
            "Executive Summary": {"overall_score": 0.65}  # Below 0.80 threshold
        }
        gate_result_low = evaluate_quality_gate(quality_scores_low, consistency_clean, threshold=0.80)
        self.assertFalse(gate_result_low["gate_passed"])
        self.assertIn("Executive Summary", gate_result_low["failing_formats"])
        self.assertFalse(gate_result_low["per_format_gate"]["Executive Summary"]["passed"])

        # FAIL scenario due to severe contradiction
        consistency_with_error = {
            "contradictions": [
                {
                    "affected_format": "LinkedIn Post",
                    "severity": "error",
                    "element_type": "metric",
                    "observed_value": "42%",
                    "expected_value": "68%"
                }
            ]
        }
        gate_result_contra = evaluate_quality_gate(quality_scores, consistency_with_error, threshold=0.80)
        self.assertFalse(gate_result_contra["gate_passed"])
        self.assertIn("LinkedIn Post", gate_result_contra["failing_formats"])

    def test_compatibility_with_existing_targeted_recovery(self):
        """Verifies that validate_and_recover_outputs flags failed formats and feeds contradictions into recovery."""
        req = TransformRequest(
            source_content=self.source,
            output_types=["Executive Summary", "LinkedIn Post"]
        )
        # Executive Summary valid, LinkedIn Post has contradiction (65% instead of 68%)
        outputs = {
            "Executive Summary": (
                "## Executive Overview\n"
                "Project CyberShield is an enterprise cybersecurity framework initiated in Q1 2026.\n\n"
                "## Key Findings\n"
                "Automated detection reduced threat response times by 68% during internal pilot testing."
            ),
            "LinkedIn Post": "Threat response times reduced by 65% in Q1 2026. #Tech"  # Contradiction
        }
        out, val_report = validate_and_recover_outputs(
            outputs=outputs,
            request=req,
            model=None,
            multimodal_parts=[],
            canonical_model=self.canonical_model
        )
        self.assertIn("cross_format_consistency", val_report)
        self.assertIn("quality_scores", val_report)
        self.assertIn("quality_gate", val_report)
        self.assertIn("claim_provenance", val_report)
        # LinkedIn Post failed quality gate due to contradiction
        self.assertIn("LinkedIn Post", val_report["quality_gate"]["failing_formats"])
        self.assertNotIn("Executive Summary", val_report["quality_gate"]["failing_formats"])

    def test_transform_flow_quality_gate_integration(self):
        """Verifies /transform (mock_transform_content) produces full quality gate and consistency report."""
        req = TransformRequest(
            source_content=self.source,
            output_types=["Executive Summary", "LinkedIn Post", "Twitter/X Post"],
            target_audience="Executive Leadership",
            tone="Professional",
            document_name="cybershield_brief.txt"
        )
        res = mock_transform_content(req)
        self.assertEqual(res.status, "success")
        self.assertIsNotNone(res.cross_format_consistency)
        self.assertIn("consistent", res.cross_format_consistency)
        self.assertIsNotNone(res.quality_score)
        self.assertIn("overall_score", res.quality_score)
        self.assertIsNotNone(res.quality_gate)
        self.assertIn("gate_passed", res.quality_gate)
        self.assertIn("per_format_gate", res.quality_gate)

        # Metadata dictionary backward compatibility
        self.assertIn("cross_format_consistency", res.metadata)
        self.assertIn("quality_score", res.metadata)
        self.assertIn("quality_gate", res.metadata)

        # Provenance contains claim_provenance and quality_score for every format
        for ot in ["Executive Summary", "LinkedIn Post", "Twitter/X Post"]:
            self.assertIn(ot, res.provenance)
            prov = res.provenance[ot]
            self.assertIn("claim_provenance", prov)
            self.assertIsInstance(prov["claim_provenance"], list)
            self.assertIn("quality_score", prov)
            self.assertIn("overall_score", prov["quality_score"])

    def test_refine_flow_quality_gate_integration(self):
        """Verifies /refine (mock_refine_content) produces quality gate, consistency report, and claim provenance."""
        req = RefineRequest(
            source_content=self.source,
            output_type="LinkedIn Post",
            current_output="[MOCK GENERATION - LINKEDIN POST]\nInitial text.",
            refinement_instruction="Emphasize the 68% threat response reduction."
        )
        res = mock_refine_content(req)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.output_type, "LinkedIn Post")
        self.assertIsNotNone(res.cross_format_consistency)
        self.assertIsNotNone(res.quality_score)
        self.assertIsNotNone(res.quality_gate)
        self.assertIn("claim_provenance", res.provenance)
        self.assertIn("quality_score", res.provenance)
        self.assertIn("cross_format_consistency", res.metadata)
        self.assertIn("quality_score", res.metadata)
        self.assertIn("quality_gate", res.metadata)


if __name__ == "__main__":
    unittest.main()




