import asyncio
from pathlib import Path
from app.services.cv_service import process_cv_file
from app.services.match_service import CandidateAnalysisContext
from app.services.scoring_engine import ScoringEngine

async def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name

    # Need just extraction and processing without force_reprocess to just grab json
    result = await process_cv_file(filename=filename, content=content, force_reprocess=True)
    resume_json = result.get("resume_json", {})
    text_val = result.get("text", "")
    
    ctx = CandidateAnalysisContext.create(
        cv_text=text_val,
        resume_json=resume_json,
        domain_repository=ScoringEngine.domain_repository
    )
    
    print("cand_tax_domain:", ctx.cand_tax_domain)
    print("cand_primary_family:", ctx.cand_primary_family)
    print("cand_families:", ctx.cand_families)

if __name__ == "__main__":
    asyncio.run(main())
