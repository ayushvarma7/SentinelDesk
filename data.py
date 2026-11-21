"""Dataset loading, cleaning and the official leakage-safe 80/20 split. FROZEN after setup."""
import os, re
import pandas as pd
from config import DATA_REPO, DATA_FILE, SEED, LANGS

LOCAL_PATH = os.getenv("SD_DATA_PATH", f"data/{DATA_FILE}")
_BR = re.compile(r"<\s*/?\s*br\s*/?\s*>", re.IGNORECASE)


def load_raw() -> pd.DataFrame:
    if os.path.exists(LOCAL_PATH):
        df = pd.read_csv(LOCAL_PATH)
        print(f"[data] loaded {LOCAL_PATH}: {len(df):,} rows")
        return df
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id=DATA_REPO, filename=DATA_FILE, repo_type="dataset")
    df = pd.read_csv(path)
    print(f"[data] downloaded {DATA_FILE}: {len(df):,} rows")
    return df


def clean_text(s) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\\n", "\n")          # dataset stores newlines as the two characters backslash + n
    s = _BR.sub("\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["body", "type", "queue", "priority"])
    for c in ("subject", "body", "answer"):
        if c in df:
            df[c] = df[c].map(clean_text)
    df["type"] = df["type"].astype(str).str.strip()
    df["queue"] = df["queue"].astype(str).str.strip()
    df["priority"] = df["priority"].astype(str).str.strip().str.lower()
    df["language"] = df["language"].astype(str).str.strip().str.lower()
    df = df[df["language"].isin(LANGS) & (df["body"].str.len() > 0)]
    return df.reset_index(drop=True)


def official_split(df: pd.DataFrame):
    """Organisers' snippet verbatim: shuffle(seed 42) -> TKT ids -> 80/20. Cleaning happens AFTER ids are assigned."""
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    idx = int(len(df) * 0.8)
    kb = clean(df.iloc[:idx])
    kb = kb[kb["answer"].str.len() > 0].reset_index(drop=True)   # 7 rows have no answer
    test = clean(df.iloc[idx:])
    return kb, test


def ticket_text(subject, body) -> str:
    subject = clean_text(subject)
    body = clean_text(body)
    return f"{subject}\n{body}" if subject else body
