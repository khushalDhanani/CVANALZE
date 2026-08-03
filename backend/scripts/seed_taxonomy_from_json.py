# backend/scripts/seed_taxonomy_from_json.py
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal, init_db
from app.core.rule_config_manager import RuleConfigManager
from app.models.taxonomy import (
    DesignationMaster,
    DesignationSynonym,
    DomainMaster,
    FamilyCompatibility,
    JobFamilyMaster,
)
from app.services.domain_embedding_service import DomainEmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_taxonomy")


def seed_taxonomy_and_vectors():
    logger.info("Initializing DB tables if not existing...")
    init_db()

    config = RuleConfigManager.load_config()
    taxonomy_rules = config.scoring.taxonomy

    if SessionLocal is None:
        logger.warning("MSSQL SessionLocal is None. Cannot seed MSSQL. Seeding pgvector directly...")
        db = None
    else:
        db = SessionLocal()

    try:
        domain_map: dict[str, DomainMaster] = {}
        family_map: dict[str, JobFamilyMaster] = {}

        # 1. Seed Canonical Domains
        logger.info("Seeding Domains...")
        for idx, domain_name in enumerate(taxonomy_rules.canonical_domains, start=1):
            code = domain_name.upper().replace(" & ", "_").replace(" ", "_").replace("/", "_")
            if db:
                dom = db.query(DomainMaster).filter(DomainMaster.domain_name == domain_name).first()
                if not dom:
                    dom = DomainMaster(
                        domain_code=code,
                        domain_name=domain_name,
                        description=f"Canonical Domain: {domain_name}",
                    )
                    db.add(dom)
                    db.flush()
                domain_map[domain_name] = dom
            else:
                domain_map[domain_name] = None

        # Ensure default domain exists
        default_dom_name = taxonomy_rules.default_domain
        if default_dom_name not in domain_map and db:
            code = default_dom_name.upper().replace(" & ", "_").replace(" ", "_")
            dom = db.query(DomainMaster).filter(DomainMaster.domain_name == default_dom_name).first()
            if not dom:
                dom = DomainMaster(
                    domain_code=code,
                    domain_name=default_dom_name,
                    description="Default Fallback Domain",
                )
                db.add(dom)
                db.flush()
            domain_map[default_dom_name] = dom

        # 2. Seed Canonical Families
        logger.info("Seeding Job Families...")
        # Map known families to domains
        family_to_domain_mapping = {
            "Software Engineering & Development": "IT & Software Services",
            "IT Infrastructure, Networking & AV Systems": "IT & Software Services",
            "Plant Electrical & Utility Maintenance": "Plant Operations & Maintenance",
            "Control & Instrumentation (C&I)": "Plant Operations & Maintenance",
            "Quality Control (QC) & Laboratory": "Quality Assurance & QC Laboratory",
            "Quality Assurance (QA)": "Quality Assurance & QC Laboratory",
            "Fire, Safety & EHS": "Environmental Health & Safety (EHS)",
            "Environment & ETP Operations": "Environmental Health & Safety (EHS)",
            "Process & Project Engineering": "Process & Project Engineering",
            "Finance & Administration": "Finance & Administration",
            "General Professional": "General Operations",
        }

        for fam_name in taxonomy_rules.canonical_families:
            dom_name = family_to_domain_mapping.get(fam_name, taxonomy_rules.default_domain)
            dom_obj = domain_map.get(dom_name)
            if db and dom_obj:
                code = fam_name.upper().replace(" & ", "_").replace(" ", "_").replace(",", "").replace("(", "").replace(")", "")
                fam = db.query(JobFamilyMaster).filter(JobFamilyMaster.family_name == fam_name).first()
                if not fam:
                    fam = JobFamilyMaster(
                        domain_id=dom_obj.domain_id,
                        family_code=code,
                        family_name=fam_name,
                        description=f"Canonical Family: {fam_name}",
                    )
                    db.add(fam)
                    db.flush()
                family_map[fam_name] = fam
            else:
                family_map[fam_name] = None

        # 3. Seed Designations & Synonyms from Vacancy and Candidate Rules
        logger.info("Seeding Designations and Synonyms...")
        designations_to_vectorize: list[tuple[str, str]] = []  # (term, category)

        # Collect designaton keywords from vacancy_rules and candidate_rules
        raw_designations: dict[str, tuple[str, list[str]]] = {}  # desig_name -> (family_name, synonyms)

        for rule in taxonomy_rules.vacancy_rules:
            fam_name = rule.family
            desig_name = rule.name.replace("_", " ").title()
            synonyms = []
            for branch in rule.branches:
                for cond in branch.conditions:
                    synonyms.extend(cond.keywords)
            raw_designations[desig_name] = (fam_name, list(set(synonyms)))

        for rule in taxonomy_rules.candidate_rules:
            for fam_name in rule.families:
                desig_name = rule.name.replace("_", " ").title()
                synonyms = []
                for branch in rule.branches:
                    for cond in branch.conditions:
                        synonyms.extend(cond.keywords)
                if desig_name in raw_designations:
                    existing_fam, existing_syns = raw_designations[desig_name]
                    raw_designations[desig_name] = (
                        existing_fam,
                        list(set(existing_syns + synonyms)),
                    )
                else:
                    raw_designations[desig_name] = (fam_name, list(set(synonyms)))

        for desig_name, (fam_name, synonyms) in raw_designations.items():
            fam_obj = family_map.get(fam_name)
            if db and fam_obj:
                code = desig_name.upper().replace(" ", "_")
                desig = db.query(DesignationMaster).filter(DesignationMaster.designation_name == desig_name).first()
                if not desig:
                    desig = DesignationMaster(
                        family_id=fam_obj.family_id,
                        designation_code=code,
                        designation_name=desig_name,
                    )
                    db.add(desig)
                    db.flush()

                # Add canonical synonym
                canon_syn = (
                    db.query(DesignationSynonym)
                    .filter(
                        DesignationSynonym.designation_id == desig.designation_id,
                        DesignationSynonym.synonym_text == desig_name,
                    )
                    .first()
                )
                if not canon_syn:
                    db.add(
                        DesignationSynonym(
                            designation_id=desig.designation_id,
                            synonym_text=desig_name,
                            is_canonical=True,
                        )
                    )

                for syn in synonyms:
                    if syn and len(syn) > 1:
                        syn_obj = (
                            db.query(DesignationSynonym)
                            .filter(
                                DesignationSynonym.designation_id == desig.designation_id,
                                DesignationSynonym.synonym_text == syn,
                            )
                            .first()
                        )
                        if not syn_obj:
                            db.add(
                                DesignationSynonym(
                                    designation_id=desig.designation_id,
                                    synonym_text=syn,
                                    is_canonical=False,
                                )
                            )

            designations_to_vectorize.append((desig_name, "job_titles"))
            for syn in synonyms:
                if syn and len(syn) > 1:
                    designations_to_vectorize.append((syn, "job_titles"))

        # 4. Seed Family Compatibilities
        logger.info("Seeding Family Compatibility Matrix...")
        if db:
            for (
                source_fam_name,
                target_fams,
            ) in taxonomy_rules.compatibility_map.items():
                src_fam = family_map.get(source_fam_name)
                if not src_fam:
                    continue
                for tgt_fam_name in target_fams:
                    tgt_fam = family_map.get(tgt_fam_name)
                    if not tgt_fam:
                        continue
                    compat = (
                        db.query(FamilyCompatibility)
                        .filter(
                            FamilyCompatibility.source_family_id == src_fam.family_id,
                            FamilyCompatibility.target_family_id == tgt_fam.family_id,
                        )
                        .first()
                    )
                    if not compat:
                        db.add(
                            FamilyCompatibility(
                                source_family_id=src_fam.family_id,
                                target_family_id=tgt_fam.family_id,
                                compatibility_score=1.0,
                                is_allowed=True,
                            )
                        )

        if db:
            db.commit()
            logger.info("MSSQL Master Taxonomy successfully seeded!")

        # 5. Seed Vector Embeddings into pgvector
        logger.info("Vectorizing designations and synonyms into pgvector domain_embeddings...")
        vector_count = 0
        for term, cat in set(designations_to_vectorize):
            try:
                DomainEmbeddingService.get_or_generate_domain_embedding(term=term, category=cat, allow_live_generation=True)
                vector_count += 1
            except Exception as exc:
                logger.warning(f"Could not generate embedding for term '{term}': {exc}")

        logger.info(f"Successfully processed {vector_count} vector embeddings in pgvector.")

    except Exception as exc:
        if db:
            db.rollback()
        logger.error(f"Error during taxonomy seeding: {exc}", exc_info=True)
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    seed_taxonomy_and_vectors()
