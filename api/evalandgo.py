"""
MustCompliance - EvalAndGo API Client
Scrape questionnaires, respondents and documents
"""
import os
import json
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime


class EvalAndGoClient:
    """Client for EvalAndGo API v3"""
    
    BASE_URL = "https://app.evalandgo.com/api/v3"
    
    def __init__(self, jwt_token: str = None):
        self.jwt_token = jwt_token or os.getenv("EVALANDGO_JWT")
        if not self.jwt_token:
            raise ValueError("JWT token required")
        
        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make API request"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.RequestException as e:
            print(f"Error {method} {endpoint}: {e}")
            return None
    
    def get(self, endpoint: str, **kwargs) -> Optional[Dict]:
        return self._request("GET", endpoint, **kwargs)
    
    def list_questionnaires(self) -> List[Dict]:
        """List all questionnaires"""
        data = self.get("/questionnaires")
        return data.get("hydra:member", []) if data else []
    
    def get_questionnaire(self, questionnaire_id: int) -> Optional[Dict]:
        """Get single questionnaire"""
        return self.get(f"/questionnaires/{questionnaire_id}")
    
    def list_questions(self, questionnaire_id: int) -> List[Dict]:
        """List all questions in questionnaire"""
        data = self.get(f"/questionnaires/{questionnaire_id}/questions")
        return data.get("hydra:member", []) if data else []
    
    def list_respondents(self, questionnaire_id: int) -> List[Dict]:
        """List all respondents for questionnaire"""
        data = self.get(f"/questionnaires/{questionnaire_id}/respondents")
        return data.get("hydra:member", []) if data else []
    
    def get_respondent(self, respondent_id: int) -> Optional[Dict]:
        """Get single respondent with all responses"""
        return self.get(f"/respondents/{respondent_id}")
    
    def download_upload(self, response_id: int) -> bytes:
        """Download uploaded file (returns ZIP content)"""
        url = f"{self.BASE_URL}/responses/upload/{response_id}/download"
        response = requests.get(url, headers=self.headers)
        return response.content if response.status_code == 200 else None


# Default JWT from user
DEFAULT_JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3NzYyNjY0NzIsImV4cCI6MTc3NzU2MjQ3Miwicm9sZXMiOlsiUk9MRV9VU0VSIl0sImlkIjo2OTAsInVzZXJuYW1lIjoiY29udGFjdEBtdXN0Y29tcGxpYW5jZS5mciJ9.Gxgv6-6a8eB62F3g304LiriRpxDwFt8EGsjORfSYwaCSFpHH93KUBCuK0kkm_vtrjZfVJJUlO9CkYF1tngxV5kVuUgdb0drHPDiV2t90BqTiPAO4LsN91KEYauAMyAOiccxtsPBVA6ja_hcdPBCNQsHfuf2hfJ6nejWDz3kldS2wVejj3zmPazzXw8SBDWC1rb0A8usPIhFPArYvWdZtomn2o9UYHNTwF0JEXpbUcRQspsM7JbbpfyYVQmy4VUUdcPopQcOdKHV8sMjJWsENlpSmEfq-VC474SaYTRFDAdwbFZ8wNbDnppyvlbLFJdXntuVFt0w4HtSNgqdrZWYuSPHLj_lqUO75PDdPatDCJmH5L8ltyDpsITkzv0NFlCgEK16kA69FrcyCdin8CiH8soJpktljDxVoh3Ok-RZl1P3Uv2AAlFHCcTBiwTXLxlEQ6tmmmtsHABkYhCDtzvL7deIagunOfpt7G9niwP6vg73FTW0SgO734wgMu1Md_F8_diBFy_MDGYYTnake89oIW8zOPiq_KS28ea-2EldPVGZMTJkpqxmJ8R6ZVJJocDAXo9VgqmGIItVL2ILDF9Ro2N1x5FnCwKQeD184Y0AvHTkPGLu4ao0yr4fE8LY6rB-Odu-ntfAdSHpEh44QioEoGpf3paGZN_JH6INJwiaxwxs"


def create_client() -> EvalAndGoClient:
    """Create EvalAndGo client with default JWT"""
    return EvalAndGoClient(DEFAULT_JWT)


# Field mapping configuration
QUESTIONNAIRE_FIELDS = {
    # Main questionnaire (303354)
    303354: {
        "nom": "cabinet_name",
        "email": "contact_email",
        "immatriculation": "numero_orias",
        "numero_tva": "tva_intracommunautaire",
        "informations": "information_cabinet",
        "rgpd": "politique_rgpd",
        "lien_capitalistique": "lien_capitalistique",
        "activites": "activites_cabinet",
        "assurance": "assurance",
        "association": "association_professionnelle",
        "reclamations": "procedure_reclamations",
        "remunerations_incitations": "remunerations",
        "representant_legaux": "representants_legaux",
        "conseillers": "conseillers",
        "clients": "clients",
        "styles": "produits_services",
    },
    # Document collection (349199)
    349199: {
        "documents": "upload_responses",
    }
}


def extract_cabinet_from_respondent(respondent: Dict, questionnaire_id: int = 303354) -> Dict:
    """Extract cabinet data from respondent"""
    data = {
        "respondent_id": respondent.get("id"),
        "questionnaire_id": questionnaire_id,
        "email": respondent.get("email"),
        "first_name": respondent.get("firstName"),
        "last_name": respondent.get("lastName"),
        "finish": respondent.get("finish"),
        "start_at": respondent.get("startAt"),
        "end_at": respondent.get("endAt"),
        "score": respondent.get("score"),
    }
    
    # Get responses
    for resp_url in respondent.get("responses", []):
        resp_id = resp_url.get("@id", "").split("/")[-1]
        resp_type = resp_url.get("@type", "")
        
        if "upload" in resp_type.lower():
            data.setdefault("uploads", []).append({
                "id": resp_id,
                "type": resp_type
            })
    
    return data


if __name__ == "__main__":
    # Test
    client = create_client()
    questionnaires = client.list_questionnaires()
    print(f"Found {len(questionnaires)} questionnaires:")
    for q in questionnaires:
        print(f"  [{q['id']}] {q['name']} - {q.get('label', '')[:50]}")