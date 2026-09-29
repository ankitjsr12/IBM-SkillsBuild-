import os
import sys
import time
import pandas as pd

# --- SENDER CONFIGURATION (FAIL-CLOSED) ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", os.environ.get("APP_PASSWORD", "")).strip()

EMAIL_SUBJECT = "AI-Assisted Case Profiling & Intelligence Research for {agency_name}"
EMAIL_BODY = """Hi {agency_name} Team,

I came across your organization while researching active investigation firms.

We have developed Detective Agentic AI—an intelligence research and pattern-matching system built specifically for investigation teams and legal researchers:

1. Modus Operandi Alignment: Cross-reference incident behavioral indicators against historical precedents using RAG vector similarity.
2. Executive PDF Dossiers: Generate structured research summaries and pattern-match breakdowns with full evidence citations.
3. Secure Case Ingestion: Ingest historical case records (.json) directly into a private vector index.

We are currently offering pilot access for qualified agencies.

Would you be open to a brief live demonstration or walkthrough this week?

Best regards,
Investigation Outreach Team
Detective Agentic AI
"""

def launch_outreach_campaign():
    print("🚀 Initializing Cold Email Outreach Campaign...")

    if not SENDER_EMAIL or not APP_PASSWORD:
        print("❌ Error: SENDER_EMAIL or GMAIL_APP_PASSWORD not set in environment. System operates in fail-closed mode.")
        sys.exit(1)

    try:
        import yagmail
        yag = yagmail.SMTP(SENDER_EMAIL, APP_PASSWORD)
        df = pd.read_csv("agency_leads.csv")
    except Exception as e:
        print(f"❌ Initialization Error: {e}")
        return

    for idx, row in df.iterrows():
        agency = row["Agency_Name"]
        recipient = row["Contact_Email"]

        body = EMAIL_BODY.format(agency_name=agency)
        subject = EMAIL_SUBJECT.format(agency_name=agency)

        try:
            # yag.send(to=recipient, subject=subject, contents=body)
            print(f"📧 [PREVIEW/READY] Email queued for: {agency} ({recipient})")
        except Exception as e:
            print(f"❌ Could not send to {agency}: {e}")

        # Safe delay between emails to avoid spam filters
        time.sleep(5)

    print("\n✅ Outreach processing complete!")

if __name__ == "__main__":
    launch_outreach_campaign()