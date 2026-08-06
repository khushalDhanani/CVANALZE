import asyncio
from pathlib import Path
from app.services.cv_service import process_cv_file
from app.services.job_taxonomy import CandidateResumeDTO, TaxonomyClassifier

async def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name

    result = await process_cv_file(filename=filename, content=content, force_reprocess=True)
    resume_json = result.get("resume_json", {})
    text_val = result.get("text", "")
    
    dto = CandidateResumeDTO.from_resume(resume_json, text_val)
    print("DTO combined text:", dto.full_text[:500])
    
    cand_domain, cand_families = TaxonomyClassifier.classify_candidate(dto)
    print("cand_tax_domain:", cand_domain)
    print("cand_families:", cand_families)

if __name__ == "__main__":
    asyncio.run(main())
