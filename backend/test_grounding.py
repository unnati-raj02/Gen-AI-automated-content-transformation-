"""
Deterministic test suite for factual grounding and claim-level unsupported-content detection.
Covers CyberShield source text, supported paraphrasing, scaffolding filtering,
unsupported qualitative/quantitative hallucinations, and existing metric regression tests.
"""

import unittest
from services.transform_service import (
    verify_factual_grounding,
    validate_output,
    extract_key_factual_tokens,
    _stem_word,
    _is_scaffolding_or_boilerplate,
    _split_into_claim_candidates
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


if __name__ == "__main__":
    unittest.main()



