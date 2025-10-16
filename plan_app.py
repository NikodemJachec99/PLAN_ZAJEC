import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone, time as dtime
import math
import heapq
from zoneinfo import ZoneInfo
import os

# --- STAŁE / KONFIG ---
HOUR_HEIGHT_PX = 65         # 1h = 65px
COMPACT_RANGE   = True      # przycinaj widok do zakresu zajęć (+/- 15 min)
TZ_WA = ZoneInfo("Europe/Warsaw")

PLAN_PATH = "plan_zajec.xlsx"
PRAKTYKI_TIDY_CANDIDATES = ["praktyki_tidy (1).xlsx", "praktyki_tidy.xlsx"]

# --- USTAWIENIA STRONY ---
st.set_page_config(page_title="Plan Zajęć ❤️", page_icon="📅", layout="centered")

# Ukryj menu i stopkę Streamlit
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- AUTO-ODŚWIEŻANIE (60 s) ---
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 1000, key="autorefresh-60s")
except Exception:
    st.markdown("<script>setTimeout(()=>window.location.reload(), 60000);</script>", unsafe_allow_html=True)

# --- UTIL: bezpieczny concat i normalizacja czasu ---
def concat_nonempty(dfs):
    dfs = [df.dropna(axis=1, how="all") for df in dfs if df is not None and not df.empty]
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True, sort=False)

def normalize_time_series(series):
    """Obsłuż HH:MM, HH:MM:SS, datetime.time; zwróć dtype=object z wartościami time lub None."""
    def parse_one(x):
        if pd.isna(x):
            return None
        if isinstance(x, dtime):
            return x
        s = str(x).strip()
        # spróbuj szybkie ścieżki
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except Exception:
                pass
        # fallback: pd.to_datetime (łapie też excellowe datetime)
        try:
            dt = pd.to_datetime(x, errors="coerce")
            if pd.isna(dt):
                return None
            # jeśli to Timestamp -> ma date+time; bierz sam time
            return (dt.to_pydatetime().time()
                    if hasattr(dt, "to_pydatetime") else None)
        except Exception:
            return None
    return series.apply(parse_one)

# --- WCZYTYWANIE DANYCH: główny plik ---
@st.cache_data(ttl=600)
def load_data(file_path: str) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=3)

    df.columns = [
        'date', 'day_of_week', 'start_time', 'end_time', 'subject', 'type',
        'degree', 'first_name', 'last_name', 'room', 'field_year', 'group',
        'info_combined', 'additional_info'
    ] + [f'unnamed_{i}' for i in range(len(df.columns) - 14)]

    df = df[['date', 'day_of_week', 'start_time', 'end_time', 'subject',
             'type', 'degree', 'first_name', 'last_name', 'room', 'group']].copy()

    # data
    df.dropna(subset=['date'], inplace=True)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    # nauczyciel / grupa
    df['instructor'] = (
        df['degree'].fillna('') + ' ' + df['first_name'].fillna('') + ' ' + df['last_name'].fillna('')
    ).str.strip()
    df['group'] = df['group'].fillna('---').astype(str)

    # GODZINY — ROBUST
    df['start_time_obj'] = normalize_time_series(df['start_time'])
    df['end_time_obj']   = normalize_time_series(df['end_time'])
    df['start_time'] = df['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if x else '')
    df['end_time']   = df['end_time_obj'].apply(  lambda x: x.strftime('%H:%M') if x else '')

    # spójność kolumn
    df['oddzial'] = ""

    df.sort_values(by=['date', 'start_time_obj'], inplace=True, na_position='last')
    return df

# --- WCZYTYWANIE DANYCH: praktyki (TIDY) ---
@st.cache_data(ttl=600)
def load_praktyki_tidy(candidates) -> pd.DataFrame:
    path_used = None
    for p in candidates:
        if os.path.exists(p):
            path_used = p
            break
    if path_used is None:
        return pd.DataFrame(columns=[
            "date","start_time","end_time","subject","instructor","room","group",
            "start_time_obj","end_time_obj","oddzial"
        ])

    dfp = pd.read_excel(path_used)

    # Ujednolicenie typów
    dfp["date"] = pd.to_datetime(dfp["date"], errors='coerce')
    dfp.dropna(subset=["date"], inplace=True)

    # Normalizacja godzin (nie zakładamy konkretnego formatu)
    if "start_time_obj" in dfp.columns and dfp["start_time_obj"].notna().any():
        dfp["start_time_obj"] = normalize_time_series(dfp["start_time_obj"])
    else:
        dfp["start_time_obj"] = normalize_time_series(dfp.get("start_time", pd.Series([None]*len(dfp))))

    if "end_time_obj" in dfp.columns and dfp["end_time_obj"].notna().any():
        dfp["end_time_obj"] = normalize_time_series(dfp["end_time_obj"])
    else:
        dfp["end_time_obj"] = normalize_time_series(dfp.get("end_time", pd.Series([None]*len(dfp))))

    # Polskie aliasy -> subject/room/instructor
    if "przedmiot" in dfp.columns:
        dfp["subject"] = dfp["przedmiot"]
    if "prowadzacy" in dfp.columns:
        dfp["instructor"] = dfp["prowadzacy"]
    if "miejsce" in dfp.columns:
        dfp["room"] = dfp["miejsce"]

    for col in ["subject","instructor","room","group","oddzial"]:
        if col not in dfp.columns:
            dfp[col] = ""

    # finalne str z godzin
    dfp["start_time"] = dfp["start_time_obj"].apply(lambda x: x.strftime("%H:%M") if x else "")
    dfp["end_time"]   = dfp["end_time_obj"].apply(  lambda x: x.strftime("%H:%M") if x else "")

    return dfp[[
        "date","start_time","end_time","subject","instructor","room","group",
        "start_time_obj","end_time_obj","oddzial"
    ]].sort_values(["date","start_time"], na_position='last')

# --- STYLE (kompakt) ---
st.markdown("""
<style>
  html { font-size: 14px; }
  body, .stApp { line-height: 1.25; }
  .stApp > header { background-color: transparent; }
  .main .block-container { padding: 0.5rem 0.6rem 3rem 0.6rem; }
  h1 { text-align:center; color:#1a202c; margin-bottom:0.6rem; font-size:1.35rem; }
  .week-range { text-align:center; font-size:1.05rem; font-weight:600; color:#2d3748; margin:0.2rem 0 0.6rem; }

  .stButton>button {
    padding: 0.25rem 0.5rem !important;
    font-size: 0.85rem !important;
    line-height: 1.1 !important;
    border-radius: 8px !important;
  }

  .day-layout { display:grid; grid-template-columns:70px 1fr; gap:0.6rem; align-items:start; }

  .timeline-rail { position:sticky; top:0; width:70px; border-right:2px solid #e2e8f0; }
  .timeline-rail-inner { position:relative; height:var(--day-height, 720px); }
  .tick { position:absolute; left:0; right:0; border-top:1px dashed #e2e8f0; }
  .tick-label { position:absolute; left:0; width:60px; text-align:right; font-size:0.72rem; color:#94a3b8; transform:translateY(-50%); padding-right:4px; }

  .calendar-canvas { position:relative; min-height:var(--day-height, 720px); border-left:2px solid #e2e8f0; }
  .event {
    position:absolute; box-sizing:border-box; padding:6px 8px;
    background:#0ea5e910; border:1px solid #38bdf8; border-radius:10px;
    overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.05);
  }
  .event .title { font-weight:700; color:#0f172a; margin-bottom:1px; font-size:0.92rem; }
  .event .meta { font-size:.72rem; color:#334155; line-height:1.15; }

  .now-line-wide { position:absolute; left:0; right:0; border-top:2px solid #ef4444; z-index:3; }
  .now-badge { position:absolute; right:6px; transform:translateY(-100%); font-size:.7rem; color:#ef4444; z-index:4; background:transparent; }

  @media (max-width: 640px) {
    html { font-size: 13px; }
    .day-layout { grid-template-columns:56px 1fr; gap:0.45rem; }
    .timeline-rail { width:56px; }
    .tick-label { width:48px; font-size:.68rem; }
    .event { padding:5px 7px; border-radius:8px; }
    .event .title { font-size:.88rem; }
    .event .meta { font-size:.68rem; }
    .stButton>button { padding:0.22rem 0.45rem !important; font-size:.82rem !important; }
  }
</style>
""", unsafe_allow_html=True)

# --- POMOCNICZE ---
def to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute

def assign_columns_and_clusters(evts):
    result = []
    active = []        # min-heap po end_min: (end_min, col, idx)
    free_cols = []     # lista wolnych kolumn
    next_col = 0
    clusters, current_cluster = [], []

    for idx, ev in enumerate(evts):
        while active and active[0][0] <= ev["start_min"]:
            _, col_finished, _ = heapq.heappop(active)
            free_cols.append(col_finished)
            free_cols.sort()
        if not active and current_cluster:
            clusters.append(current_cluster)
            current_cluster = []

        col = free_cols.pop(0) if free_cols else next_col
        if col == next_col: next_col += 1

        heapq.heappush(active, (ev["end_min"], col, idx))
        result.append({**ev, "col": col, "cluster_id": -1})
        current_cluster.append((idx, ev["start_min"], ev["end_min"], col))

    if current_cluster:
        clusters.append(current_cluster)

    cluster_cols = {}
    for c_id, items in enumerate(clusters):
        points = []
        for _, s, e, _ in items:
            points.append((s, 1))
            points.append((e, -1))
        points.sort(key=lambda x: (x[0], -x[1]))
        cur = peak = 0
        for _, d in points:
            cur += d
            peak = max(peak, cur)
        cluster_cols[c_id] = max(1, peak)
        for idx, *_ in items:
            result[idx]["cluster_id"] = c_id

    return result, cluster_cols

# --- APLIKACJA ---
try:
    df_main = load_data(PLAN_PATH)
    df_pr   = load_praktyki_tidy(PRAKTYKI_TIDY_CANDIDATES)

    # Połącz źródła BEZ ostrzeżeń
    df = concat_nonempty([df_main, df_pr])

    st.title("Plan Zajęć ❤️")

    # Czas Warszawy
    now_dt = datetime.now(timezone.utc).astimezone(TZ_WA)
    today = now_dt.date()

    # Stan sesji (Pon–Pt)
    if 'current_week_start' not in st.session_state:
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
    if 'selected_day_offset' not in st.session_state:
        st.session_state.selected_day_offset = min(today.weekday(), 4)  # jeśli sob/ndz → Pt

    # Nawigacja tygodnia
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=6)

    nav_cols = st.columns([1, 1, 4, 1])
    if nav_cols[0].button("⬅️ Poprzedni", use_container_width=True):
        st.session_state.current_week_start -= timedelta(days=7)
        st.rerun()
    if nav_cols[1].button("📍 Dziś", use_container_width=True):
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
        st.session_state.selected_day_offset = min(today.weekday(), 4)
        st.rerun()
    nav_cols[2].markdown(f"<div class='week-range'>{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m.%Y')}</div>", unsafe_allow_html=True)
    if nav_cols[3].button("Następny ➡️", use_container_width=True):
        st.session_state.current_week_start += timedelta(days=7)
        st.rerun()

    # (opcjonalnie) filtr
    filter_magdalenki = st.checkbox("**:red[Grupy Magdalenki]**", value=False)

    # Skala pionowa
    PX_PER_MIN = HOUR_HEIGHT_PX / 60.0

    # Zakładki Pon–Pt
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz"]
    visible_offsets = [0, 1, 2, 3, 4]
    day_tabs = st.columns(len(visible_offsets))
    for i, off in enumerate(visible_offsets):
        current_day_date = week_start + timedelta(days=off)
        if day_tabs[i].button(f"{days_of_week_pl[off]} {current_day_date.day}", use_container_width=True):
            st.session_state.selected_day_offset = off
            st.rerun()

    # Filtrowanie tylko na bazowym planie
    df_src = df_main
    if filter_magdalenki:
        def _is_whole_year(g: str) -> bool:
            s = (g or "").strip().lower()
            return (s in {"---", "rok", "wszyscy", "all", "year"}) or ("rok" in s) or ("wsz" in s)
        def _keep_row(grp: str) -> bool:
            s = (grp or "").strip().lower()
            if _is_whole_year(s):
                return True
            if any(ch.isdigit() for ch in s):
                return s == "11" or s.startswith("11")
            return s == "d" or s.startswith("d")
        df_src = df_main[df_main["group"].apply(_keep_row)]

    # Final: bazowy (po filtrze) + praktyki tidy
    df_all = concat_nonempty([df_src, df_pr])

    # Upewnij się, że 'date' to datetime64[ns]
    if not pd.api.types.is_datetime64_any_dtype(df_all["date"]):
        df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")

    # Dzień widoku
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_offset)
    day_events = df_all[df_all['date'].dt.date == selected_day_date]

    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    # ---- OŚ CZASU + PŁÓTNO KALENDARZA ----
    base_start, base_end = dtime(7, 0), dtime(21, 0)
    base_start_m, base_end_m = to_minutes(base_start), to_minutes(base_end)

    if not day_events.empty and COMPACT_RANGE:
        ev_start_m = min(day_events['start_time_obj'].dropna().map(to_minutes)) if day_events['start_time_obj'].notna().any() else base_start_m
        ev_end_m   = max(day_events['end_time_obj'].dropna().map(to_minutes))   if day_events['end_time_obj'].notna().any()   else base_end_m
        start_m = max(base_start_m, int(math.floor((ev_start_m - 15) / 60) * 60))
        end_m   = min(base_end_m,  int(math.ceil((ev_end_m + 15) / 60) * 60))
    else:
        if not day_events.empty:
            ev_min = day_events['start_time_obj'].dropna()
            ev_max = day_events['end_time_obj'].dropna()
            start_m = min([base_start_m] + ([min(map(to_minutes, ev_min))] if len(ev_min) else []))
            end_m   = max([base_end_m]   + ([max(map(to_minutes, ev_max))] if len(ev_max) else []))
        else:
            start_m, end_m = base_start_m, base_end_m

    duration = max(60, end_m - start_m)
    PX_PER_MIN = HOUR_HEIGHT_PX / 60.0
    height_px = duration * PX_PER_MIN

    # Ticki
    first_tick_h = math.ceil(start_m / 60)
    last_tick_h  = math.floor(end_m / 60)
    ticks_html = []
    for h in range(first_tick_h, last_tick_h + 1):
        top = (h * 60 - start_m) * PX_PER_MIN
        ticks_html.append(f"<div class='tick' style='top:{top:.2f}px'></div>")
        ticks_html.append(f"<div class='tick-label' style='top:{top:.2f}px'>{h:02d}:00</div>")

    # Eventy
    def safe_get(row, key, default=""):
        return row[key] if key in row and pd.notna(row[key]) else default

    events = []
    for _, e in day_events.iterrows():
        if pd.isna(e.get('start_time_obj')) or pd.isna(e.get('end_time_obj')):
            continue
        events.append({
            "start_min": to_minutes(e['start_time_obj']),
            "end_min": to_minutes(e['end_time_obj']),
            "subject": safe_get(e, "subject"),
            "instructor": safe_get(e, "instructor"),
            "room": safe_get(e, "room"),
            "group": safe_get(e, "group"),
            "oddzial": safe_get(e, "oddzial"),
            "start_str": safe_get(e, "start_time", e['start_time_obj'].strftime("%H:%M")),
            "end_str": safe_get(e, "end_time",   e['end_time_obj'].strftime("%H:%M")),
        })
    events.sort(key=lambda x: (x["start_min"], x["end_min"]))

    # Kolumny + klastry
    def assign_columns_and_clusters_local(evts):
        result = []
        active = []
        free_cols = []
        next_col = 0
        clusters, current_cluster = [], []
        for idx, ev in enumerate(evts):
            while active and active[0][0] <= ev["start_min"]:
                _, col_finished, _ = heapq.heappop(active)
                free_cols.append(col_finished); free_cols.sort()
            if not active and current_cluster:
                clusters.append(current_cluster); current_cluster = []
            col = free_cols.pop(0) if free_cols else next_col
            if col == next_col: next_col += 1
            heapq.heappush(active, (ev["end_min"], col, idx))
            result.append({**ev, "col": col, "cluster_id": -1})
            current_cluster.append((idx, ev["start_min"], ev["end_min"], col))
        if current_cluster: clusters.append(current_cluster)
        cluster_cols = {}
        for c_id, items in enumerate(clusters):
            points = []
            for _, s, e, _ in items:
                points.append((s, 1)); points.append((e, -1))
            points.sort(key=lambda x: (x[0], -x[1]))
            cur = peak = 0
            for _, d in points:
                cur += d; peak = max(peak, cur)
            cluster_cols[c_id] = max(peak, 1)
            for idx, *_ in items:
                result[idx]["cluster_id"] = c_id
        return result, cluster_cols

    positioned, cluster_cols = assign_columns_and_clusters_local(events)

    # Render eventów (Oddział w meta)
    events_html_parts = []
    for ev in positioned:
        total_cols = max(1, cluster_cols.get(ev["cluster_id"], 1))
        width_pct = 100 / total_cols
        left_pct = ev["col"] * width_pct
        top = (ev["start_min"] - start_m) * PX_PER_MIN
        height = max(34, (ev["end_min"] - ev["start_min"]) * PX_PER_MIN)

        meta_parts = [f"{ev['start_str']}–{ev['end_str']}"]
        if ev.get("room"):    meta_parts.append(f"Sala {ev['room']}")
        if ev.get("group"):   meta_parts.append(f"Gr {ev['group']}")
        if ev.get("oddzial"): meta_parts.append(f"Oddział {ev['oddzial']}")
        meta_line = " • ".join(meta_parts)
        instructor_line = ev.get("instructor","")

        part = (
            f"<div class='event' style='top:{top:.2f}px;height:{height:.2f}px;"
            f"left:calc({left_pct}% + 2px);width:calc({width_pct}% - 6px);'>"
            f"<div class='title'>{ev['subject']}</div>"
            f"<div class='meta'>{meta_line}<br>{instructor_line}</div>"
            f"</div>"
        )
        events_html_parts.append(part)
    events_html = "".join(events_html_parts)

    # Linia TERAZ
    now_wide_html = ""
    if selected_day_date == today:
        now_dt_line = datetime.now(timezone.utc).astimezone(TZ_WA)
        now_m = now_dt_line.hour * 60 + now_dt_line.minute
        top_now = max(0, min(height_px, (now_m - start_m) * PX_PER_MIN))
        now_wide_html = (
            f"<div class='now-line-wide' style='top:{top_now:.2f}px'></div>"
            f"<div class='now-badge' style='top:{top_now:.2f}px'>Teraz {now_dt_line.strftime('%H:%M')}</div>"
        )

    # Layout
    day_layout_html = (
        f"<div class='day-layout' style='--day-height:{height_px:.2f}px'>"
        f"<div class='timeline-rail'><div class='timeline-rail-inner' style='height:{height_px:.2f}px'>{''.join(ticks_html)}</div></div>"
        f"<div class='calendar-canvas' style='min-height:{height_px:.2f}px'>{now_wide_html}{events_html if events_html else '<div style=\"padding:8px;color:#64748b;\">Brak zajęć</div>'}</div>"
        f"</div>"
    )
    st.markdown(day_layout_html, unsafe_allow_html=True)

    # Auto-scroll do „TERAZ”
    if selected_day_date == today:
        st.markdown("""
        <script>
          const el = document.querySelector('.now-line-wide');
          if (el) { setTimeout(()=>el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 10); }
        </script>
        """, unsafe_allow_html=True)

except FileNotFoundError:
    st.error("Nie znaleziono wymaganych plików Excel obok skryptu.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
