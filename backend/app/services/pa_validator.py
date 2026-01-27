# validation/pa_validator.py
from typing import Dict, List, Any, Tuple
from datetime import datetime
import json

class PAValidator:
    """Validates patient documentation against payer policy criteria"""
    
    def __init__(self, policy_rules: Dict[str, Any]):
        """
        Initialize validator with policy rules
        
        Args:
            policy_rules: The extracted policy criteria from RAG pipeline
        """
        self.policy = policy_rules
        self.validation_results = {
            "overall_status": "UNKNOWN",
            "criteria_met": [],
            "criteria_not_met": [],
            "missing_documentation": [],
            "recommendations": [],
            "score": 0,
            "max_score": 0
        }
    
    def validate_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate patient documentation against policy criteria
        
        Args:
            patient_data: Patient analysis from document extraction
            
        Returns:
            Comprehensive validation results
        """
        requirements = patient_data.get("analysis", {}).get("requirements", {})
        
        # Reset results
        self.validation_results = {
            "overall_status": "UNKNOWN",
            "criteria_met": [],
            "criteria_not_met": [],
            "missing_documentation": [],
            "recommendations": [],
            "score": 0,
            "max_score": 0
        }
        
        # Validate each criterion
        self._validate_clinical_indications(requirements)
        self._validate_imaging_requirements(requirements)
        self._validate_conservative_treatment(requirements)
        self._validate_documentation(requirements)
        self._validate_exclusions(requirements)
        
        # Calculate overall status
        self._calculate_status()
        
        return self.validation_results
    
    def _validate_clinical_indications(self, requirements: Dict) -> None:
        """Check if patient has documented diagnosis matching policy"""
        self.validation_results["max_score"] += 20
        
        # In real implementation, would check ICD-10 codes
        # For now, assume diagnosis is documented if symptom_duration exists
        if requirements.get("symptom_duration_months", 0) > 0:
            self.validation_results["criteria_met"].append({
                "criterion": "Clinical Indication",
                "status": "MET",
                "details": "Patient has documented knee symptoms requiring evaluation",
                "points": 20
            })
            self.validation_results["score"] += 20
        else:
            self.validation_results["criteria_not_met"].append({
                "criterion": "Clinical Indication",
                "status": "NOT MET",
                "details": "No documented diagnosis found",
                "points": 0
            })
    
    def _validate_imaging_requirements(self, requirements: Dict) -> None:
        """Validate X-ray requirements per policy"""
        self.validation_results["max_score"] += 20
        
        imaging = requirements.get("imaging", {})
        
        if not imaging.get("documented"):
            self.validation_results["criteria_not_met"].append({
                "criterion": "Imaging Requirement",
                "status": "NOT MET",
                "details": "No X-ray documented",
                "required": "Weight-bearing X-rays within 60 days",
                "points": 0
            })
            self.validation_results["missing_documentation"].append(
                "X-ray report (must be within 60 days)"
            )
            return
        
        # Check if X-ray is within 60 days (2 months)
        months_ago = imaging.get("months_ago", 999)
        
        if months_ago <= 2:  # Within 60 days
            self.validation_results["criteria_met"].append({
                "criterion": "Imaging Requirement",
                "status": "MET",
                "details": f"X-ray documented {months_ago} month(s) ago - within 60-day requirement",
                "points": 20
            })
            self.validation_results["score"] += 20
        else:
            self.validation_results["criteria_not_met"].append({
                "criterion": "Imaging Requirement",
                "status": "NOT MET",
                "details": f"X-ray is {months_ago} months old - exceeds 60-day requirement",
                "required": "X-ray must be within 60 days",
                "points": 0
            })
            self.validation_results["recommendations"].append(
                "Order new weight-bearing X-rays of the knee"
            )
    
    def _validate_conservative_treatment(self, requirements: Dict) -> None:
        """Validate 6-week conservative treatment requirement"""
        self.validation_results["max_score"] += 40
        
        conservative = requirements.get("conservative_therapy", {})
        pt = conservative.get("physical_therapy", {})
        nsaids = conservative.get("nsaids", {})
        
        # Check Physical Therapy
        pt_attempted = pt.get("attempted", False)
        pt_duration_weeks = pt.get("duration_weeks", 0)
        
        # Check NSAIDs
        nsaid_documented = nsaids.get("documented", False)
        
        # Policy requires 6 weeks + at least 2 of: PT (6 sessions), NSAIDs (4 weeks), activity mod, bracing
        total_points = 0
        modalities_tried = 0
        
        # Physical Therapy validation
        if pt_attempted and pt_duration_weeks >= 6:
            self.validation_results["criteria_met"].append({
                "criterion": "Physical Therapy",
                "status": "MET",
                "details": f"Completed {pt_duration_weeks} weeks of PT (minimum 6 weeks required)",
                "points": 20
            })
            total_points += 20
            modalities_tried += 1
        elif pt_attempted:
            self.validation_results["criteria_not_met"].append({
                "criterion": "Physical Therapy Duration",
                "status": "PARTIAL",
                "details": f"Only {pt_duration_weeks} weeks documented (6 weeks required)",
                "points": 10
            })
            total_points += 10
            modalities_tried += 1
        
        # NSAIDs validation
        if nsaid_documented:
            self.validation_results["criteria_met"].append({
                "criterion": "NSAIDs/Analgesics",
                "status": "MET",
                "details": "NSAID trial documented",
                "points": 20
            })
            total_points += 20
            modalities_tried += 1
        
        # Overall conservative treatment assessment
        if modalities_tried >= 2 and pt_duration_weeks >= 6:
            self.validation_results["criteria_met"].append({
                "criterion": "Conservative Treatment (6 weeks, 2+ modalities)",
                "status": "MET",
                "details": f"Patient completed {modalities_tried} treatment modalities over {pt_duration_weeks} weeks",
                "points": 0  # Already counted above
            })
        else:
            self.validation_results["criteria_not_met"].append({
                "criterion": "Conservative Treatment",
                "status": "NOT MET",
                "details": f"Only {modalities_tried} modality documented, or insufficient duration",
                "required": "Minimum 6 weeks + at least 2 of: PT (6 sessions), NSAIDs (4 weeks), activity modification, bracing",
                "points": 0
            })
            self.validation_results["recommendations"].append(
                "Document additional conservative treatments (activity modification, bracing, injections)"
            )
        
        self.validation_results["score"] += total_points
    
    def _validate_documentation(self, requirements: Dict) -> None:
        """Check if required documentation is present"""
        self.validation_results["max_score"] += 20
        
        # Required per policy:
        # - Clinical notes within 30 days
        # - Physical exam findings
        # - Duration and character of symptoms
        # - Conservative treatment records
        # - X-ray report
        
        evidence_notes = requirements.get("evidence_notes", [])
        
        has_clinical_notes = any("patient" in note.lower() for note in evidence_notes)
        has_pt_records = requirements.get("conservative_therapy", {}).get("physical_therapy", {}).get("attempted", False)
        has_xray = requirements.get("imaging", {}).get("documented", False)
        has_functional_impact = requirements.get("functional_impairment", {}).get("documented", False)
        
        documentation_score = 0
        
        if has_clinical_notes:
            documentation_score += 5
        else:
            self.validation_results["missing_documentation"].append(
                "Recent clinical notes (within 30 days) with H&P"
            )
        
        if has_pt_records:
            documentation_score += 5
        else:
            self.validation_results["missing_documentation"].append(
                "Physical therapy notes with dates and sessions"
            )
        
        if has_xray:
            documentation_score += 5
        else:
            self.validation_results["missing_documentation"].append(
                "X-ray report within 60 days"
            )
        
        if has_functional_impact:
            documentation_score += 5
            self.validation_results["criteria_met"].append({
                "criterion": "Functional Impairment Documented",
                "status": "MET",
                "details": "Patient has documented functional limitations",
                "points": 0
            })
        
        self.validation_results["score"] += documentation_score
        
        if documentation_score >= 15:
            self.validation_results["criteria_met"].append({
                "criterion": "Documentation Requirements",
                "status": "MET",
                "details": "Sufficient documentation present",
                "points": 20
            })
            self.validation_results["score"] += 5
        else:
            self.validation_results["criteria_not_met"].append({
                "criterion": "Documentation Requirements",
                "status": "INCOMPLETE",
                "details": "Missing some required documentation",
                "points": 0
            })
    
    def _validate_exclusions(self, requirements: Dict) -> None:
        """Check if any exclusion criteria apply"""
        # Policy exclusions:
        # - Routine screening without symptoms
        # - Isolated anterior knee pain without mechanical symptoms
        # - Mild OA with no surgical planning
        # - Worker's comp without ortho eval
        # - Patient declines surgery
        
        # This would require additional patient data in real implementation
        # For now, just note that exclusions should be checked
        self.validation_results["recommendations"].append(
            "Verify no exclusion criteria apply (routine screening, isolated anterior knee pain, etc.)"
        )
    
    def _calculate_status(self) -> None:
        """Calculate overall PA status"""
        score = self.validation_results["score"]
        max_score = self.validation_results["max_score"]
        
        if max_score == 0:
            percentage = 0
        else:
            percentage = (score / max_score) * 100
        
        self.validation_results["percentage"] = round(percentage, 1)
        
        if percentage >= 90:
            self.validation_results["overall_status"] = "APPROVED"
            self.validation_results["decision"] = "Prior authorization criteria met"
        elif percentage >= 70:
            self.validation_results["overall_status"] = "LIKELY APPROVED"
            self.validation_results["decision"] = "Most criteria met, minor gaps in documentation"
        elif percentage >= 50:
            self.validation_results["overall_status"] = "PENDING"
            self.validation_results["decision"] = "Additional documentation or treatment required"
        else:
            self.validation_results["overall_status"] = "DENIED"
            self.validation_results["decision"] = "Does not meet medical necessity criteria"
    
    def generate_report(self) -> str:
        """Generate human-readable validation report"""
        results = self.validation_results
        
        report = f"""
PRIOR AUTHORIZATION VALIDATION REPORT
=====================================
Overall Status: {results['overall_status']}
Score: {results['score']}/{results['max_score']} ({results.get('percentage', 0)}%)
Decision: {results.get('decision', 'Unknown')}

CRITERIA MET ({len(results['criteria_met'])}):
"""
        for item in results['criteria_met']:
            report += f"  ✓ {item['criterion']}: {item['details']}\n"
        
        report += f"\nCRITERIA NOT MET ({len(results['criteria_not_met'])}):\n"
        for item in results['criteria_not_met']:
            report += f"  ✗ {item['criterion']}: {item['details']}\n"
            if 'required' in item:
                report += f"    Required: {item['required']}\n"
        
        if results['missing_documentation']:
            report += f"\nMISSING DOCUMENTATION:\n"
            for doc in results['missing_documentation']:
                report += f"  - {doc}\n"
        
        if results['recommendations']:
            report += f"\nRECOMMENDATIONS:\n"
            for rec in results['recommendations']:
                report += f"  → {rec}\n"
        
        return report


# Usage example
def validate_pa_request(policy_rules: Dict, patient_data: Dict) -> Dict:
    """
    Main validation function
    
    Args:
        policy_rules: Extracted policy from RAG pipeline
        patient_data: Patient analysis from document extraction
        
    Returns:
        Validation results
    """
    validator = PAValidator(policy_rules)
    results = validator.validate_patient(patient_data)
    
    # Add report
    results["report"] = validator.generate_report()
    
    return results

## This will eat my two objects I made... 