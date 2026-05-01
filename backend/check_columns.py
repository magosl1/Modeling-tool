from sqlalchemy import text

from app.db.base import SessionLocal

db = SessionLocal()
result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='uploaded_files' ORDER BY ordinal_position"))
cols = [r[0] for r in result]
print("Columns:", cols)

# Add missing columns if needed
missing = []
if 'entity_id' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN entity_id VARCHAR(36)")
if 'file_path' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN file_path VARCHAR(500)")
if 'file_size_bytes' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN file_size_bytes INTEGER NOT NULL DEFAULT 0")
if 'is_ignored' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN is_ignored BOOLEAN NOT NULL DEFAULT false")
if 'ai_analysis_json' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN ai_analysis_json JSON")
if 'missing_inputs_json' not in cols:
    missing.append("ALTER TABLE uploaded_files ADD COLUMN missing_inputs_json JSON")

for sql in missing:
    print(f"Running: {sql}")
    db.execute(text(sql))
    db.commit()

# Make s3_key nullable
print("Making s3_key nullable...")
db.execute(text("ALTER TABLE uploaded_files ALTER COLUMN s3_key DROP NOT NULL"))
db.commit()

# Add foreign key
print("Adding foreign key...")
try:
    db.execute(text("ALTER TABLE uploaded_files ADD CONSTRAINT fk_uploaded_files_entity_id FOREIGN KEY (entity_id) REFERENCES entities (id) ON DELETE CASCADE"))
    db.commit()
    print("FK added.")
except Exception as e:
    print(f"FK might already exist: {e}")
    db.rollback()

print("Done. Missing columns added:", [s.split("COLUMN ")[1].split(" ")[0] for s in missing] if missing else "none")
