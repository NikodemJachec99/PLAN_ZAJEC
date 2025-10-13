import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone, time as dtime
import math
import heapq
import re
import os
from zoneinfo import ZoneInfo

# --- STAŁE DLA GĘSTOŚCI WIDOKU ---
HOUR_HEIGHT_PX = 65         # 1h = 65px
COMPACT_RANGE = True        # przycinaj widok do zakresu zajęć (+/- 15 min)
TZ_WA = ZoneInfo("Europe/Warsaw")

# --- NAZWY PLIKÓW ---
MAIN_PLAN_FILE = "plan_zajec.xlsx"
PRACTICAL_CANDIDATES = [
    "Pi_s_II_sem.-zimowy_26.09.2025 (1).xlsx",
    "/mnt/data/Pi_s_II_sem.-zimowy_26.09.2025 (1).xlsx",
    "praktyki.xlsx",
]

# --- STRONA ---
st.set_page_config(page_title="Plan Zajęć ❤️", page_icon="📅", layout="centered")

# --- AUTO-ODŚWIEŻANIE (60 s) ---
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 1000, key="autorefresh-60s")
except Exception:
    st.markdown("<script>setTimeout(()=>window.location.reload(), 60000);</script>", unsafe_allow_html=True)

# =========================
# PARSERY
# =========================
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
    df.dropna(subset=['date'], inplace=True)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    df['instructor'] = (
        df['degree'].fillna('') + ' ' + df['first_name'].fillna('') + ' ' + df['last_name'].fillna('')
    ).str.strip()
    df['group'] = df['group'].fillna('---').astype(str)

    df['start_time_obj'] = pd.to_datetime(df['start_time'], format='%H:%M:%S', errors='coerce').dt.time
    df['end_time_obj']   = pd.to_datetime(df['end_time'],   format='%H:%M:%S', errors='coerce').dt.time
    df['start_time'] = df['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')
    df['end_time']   = df['end_time_obj'].apply(  lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')

    df.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df

def _norm(s: str) -> str:
    return (s.replace('Ą','A').replace('Ć','C').replace('Ę','E').replace('Ł','L')
             .replace('Ń','N').replace('Ó','O').replace('Ś','S').replace('Ż','Z').replace('Ź','Z'))

MONTHS_PL = {
    'STYCZEN':1, 'LUTY':2, 'MARZEC':3, 'KWIECIEN':4, 'MAJ':5, 'CZERWIEC':6,
    'LIPIEC':7, 'SIERPIEN':8, 'WRZESIEN':9, 'PAZDZIERNIK':10, 'LISTOPAD':11, 'GRUDZIEN':12
}

def _month_from_label(lbl):
    if not isinstance(lbl, str): return None
    return MONTHS_PL.get(_norm(lbl.strip().upper()))

def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

@st.cache_data(ttl=600)
def load_practicals_group11_precise(file_path: str) -> pd.DataFrame:
    """
    Parser praktyk *konkretnej* struktury, zgodnie z Twoim opisem:
    - Wiersz 2: miesiące (napisy)
    - Wiersz 4: dni miesiąca (liczby)
    - Wiersz 16: ZAWSZE dane grupy 11 (fallback: znajdź '11' w kol. 0)
    - Wiersze 21..39: słownik KOD -> OPIS zajęć
    - Komórki grupy 11 mogą mieć kilka zakresów czasu (np. 'CSM7 8:00-11:45; UP 12:00-14:00')
    """
    raw = pd.read_excel(file_path, sheet_name="grafik", header=None)

    rows, cols = raw.shape

    # --- 1) MAPA KOD -> OPIS z wierszy 21..39 ---
    code_map = {}
    for r in range(21, min(40, rows)):  # 21..39
        # sprawdź kilka pierwszych kolumn, bo bywa różnie rozmieszczone
        for c in range(0, min(6, cols)):
            cell = raw.iat[r, c]
            if isinstance(cell, str) and cell.strip():
                s = " ".join(cell.split())
                # Spróbuj "KOD - opis", "KOD opis", "KOD: opis"
                # Znormalizuj do porównań, ale zachowaj oryginał do opisu
                s_norm = _norm(s).strip()
                m = re.match(r'^([A-Za-z0-9]{2,10})\s*[-–:]*\s*(.+)$', s_norm)
                if m:
                    code = m.group(1).upper()
                    desc = m.group(2).strip()
                    if code and code not in code_map:
                        code_map[code] = desc
                else:
                    # e.g. "CSM7" samo w komórce, opis może być w sąsiedniej kolumnie
                    m2 = re.match(r'^([A-Za-z0-9]{2,10})$', s_norm)
                    if m2:
                        code = m2.group(1).upper()
                        # poszukaj opisu obok
                        neigh = None
                        for cc in range(c+1, min(c+3, cols)):
                            cell2 = raw.iat[r, cc]
                            if isinstance(cell2, str) and cell2.strip():
                                neigh = " ".join(cell2.split())
                                break
                        if code and neigh and code not in code_map:
                            code_map[code] = _norm(neigh).strip()
    # --- 2) KOLUMNA -> DATA (miesiąc w wierszu 2, dzień w 4) ---
    col_date = {}
    current_month_num = None
    for c in range(1, cols):
        mcell = raw.iat[2, c] if 2 < rows else None
        if isinstance(mcell, str) and mcell.strip():
            mm = _month_from_label(mcell)
            if mm:
                current_month_num = mm
        d = raw.iat[4, c] if 4 < rows else None
        if pd.notna(d) and current_month_num is not None:
            try:
                day = int(str(d).strip())
                # rok: jesień (>=10) to pierwszy rok, <10 to drugi
                # Spróbuj znaleźć "YYYY/YYYY" w okolicy A2/A1; jak nie ma, załóż bieżący +/-
                header_text = str(raw.iat[1, 0]) if (rows > 1 and pd.notna(raw.iat[1, 0])) else ""
                mm = re.search(r'(20\d{2})/(20\d{2})', header_text)
                if mm:
                    start_year, end_year = int(mm.group(1)), int(mm.group(2))
                else:
                    # fallback: prosta heurystyka roku akademickiego
                    today = datetime.now().date()
                    start_year = today.year if today.month >= 10 else today.year - 1
                    end_year = start_year + 1
                year = start_year if current_month_num >= 10 else end_year
                col_date[c] = pd.to_datetime(f"{year}-{current_month_num:02d}-{day:02d}").date()
            except Exception:
                pass

    # --- 3) WIERSZ GRUPY 11: zawsze 16 (0-based = 16), ale zróbmy fallback ---
    grp_row_idx = 16 if rows > 16 else None
    if grp_row_idx is None or not str(raw.iat[grp_row_idx, 0]).strip():
        # fallback: szukaj '11' w pierwszej kolumnie
        for i, v in raw.iloc[:, 0].items():
            if str(v).strip().isdigit() and int(v) == 11:
                grp_row_idx = i
                break
    if grp_row_idx is None:
        return pd.DataFrame(columns=["date","subject","instructor","room","group",
                                     "start_time_obj","end_time_obj","start_time","end_time"])

    # --- 4) CZYTANIE KOMÓREK W WIERSZU GRUPY 11 ---
    time_re = re.compile(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})')
    code_re = re.compile(r'\b([A-Za-z]{2,}[0-9]{0,3})\b')  # np. CSM7, UP, itp.
    rows_out = []

    row = raw.iloc[grp_row_idx, :]
    for c, the_date in col_date.items():
        cell = row.iloc[c]
        if pd.isna(cell):
            continue

        # rozbij na segmenty: ';' lub nowa linia
        pieces = re.split(r'[;\n]+', str(cell))
        for piece in pieces:
            s = " ".join(str(piece).split())
            if not s:
                continue

            # znajdź wszystkie przedziały czasu w segmencie
            times = list(time_re.finditer(s))
            if not times:
                continue

            # przygotuj label: usuń "godz." i zakresy godzin, zbierz kod (do mapy)
            s_clean = re.sub(r'(?i)godz\.\s*', '', s)
            for m in times:
                s_clean = s_clean.replace(m.group(0), "")
            s_clean = s_clean.strip(" -–•.,;")

            # wyłuskaj kod (jeśli jest)
            code_match = code_re.search(s_clean.upper())
            code = code_match.group(1).upper() if code_match else None

            # docelowy subject: opis z mapy, albo „Praktyki [kod]”, albo czyszczony tekst
            if code and code in code_map:
                subject_label = code_map[code]
            elif code:
                subject_label = f"Praktyki {code}"
            else:
                subject_label = s_clean if s_clean else "Zajęcia praktyczne"

            # wygeneruj event dla każdego zakresu czasu
            for m in times:
                start_str, end_str = m.group(1), m.group(2)
                try:
                    stime = pd.to_datetime(start_str, format="%H:%M").time()
                    etime = pd.to_datetime(end_str,   format="%H:%M").time()
                except Exception:
                    continue

                rows_out.append({
                    "date": pd.to_datetime(the_date),
                    "subject": subject_label,
                    "instructor": "",
                    "room": "",
                    "group": "11",
                    "start_time_obj": stime,
                    "end_time_obj": etime,
                    "start_time": stime.strftime("%H:%M"),
                    "end_time": etime.strftime("%H:%M"),
                })

    out = pd.DataFrame(rows_out)
    if not out.empty:
        out.sort_values(by=["date", "start_time_obj"], inplace=True)
        out.reset_index(drop=True, inplace=True)
    return out

# =========================
# STYLE (jak było)
# =========================
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

# =========================
# RYSOWANIE / LOGIKA UI (bez zmian funkcjonalnych poza scalamy df_main + df_pr)
# =========================
def to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute

def assign_columns_and_clusters(evts):
    result = []
    active = []
    free_cols = []
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
            points.append((s, 1)); points.append((e, -1))
        points.sort(key=lambda x: (x[0], -x[1]))
        cur = peak = 0
        for _, d in points:
            cur += d; peak = max(peak, cur)
        cluster_cols[c_id] = max(1, peak)
        for idx, *_ in items:
            result[idx]["cluster_id"] = c_id
    return result, cluster_cols

try:
    # Główny plan
    df_main = load_data(MAIN_PLAN_FILE)

    # Praktyki (grupa 11)
    df_pr = pd.DataFrame()
    prat_file = _first_existing(PRACTICAL_CANDIDATES)
    if prat_file:
        try:
            df_pr = load_practicals_group11_precise(prat_file)
        except Exception:
            df_pr = pd.DataFrame()

    st.title("Plan Zajęć ❤️")

    # Czas Warszawy
    now_dt = datetime.now(timezone.utc).astimezone(TZ_WA)
    today = now_dt.date()

    # Stan sesji
    if 'current_week_start' not in st.session_state:
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
    if 'selected_day_index' not in st.session_state:
        st.session_state.selected_day_index = today.weekday()

    # Nawigacja tygodnia
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=6)

    nav_cols = st.columns([1, 1, 4, 1])
    if nav_cols[0].button("⬅️ Poprzedni", use_container_width=True):
        st.session_state.current_week_start -= timedelta(days=7)
        st.rerun()
    if nav_cols[1].button("📍 Dziś", use_container_width=True):
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
        st.session_state.selected_day_index = today.weekday()
        st.rerun()
    nav_cols[2].markdown(f"<div class='week-range'>{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m.%Y')}</div>", unsafe_allow_html=True)
    if nav_cols[3].button("Następny ➡️", use_container_width=True):
        st.session_state.current_week_start += timedelta(days=7)
        st.rerun()

    # ✅ Checkbox „Grupy Magdalenki” – działa WYŁĄCZNIE na df_main
    filter_magdalenki = st.checkbox("**:red[Grupy Magdalenki]**", value=False)

    # Zastosuj filtr tylko do df_main
    df_main_src = df_main
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

        df_main_src = df_main[df_main["group"].apply(_keep_row)]

    # Doklej praktyki (zawsze gr. 11)
    if not df_pr.empty:
        df_all = pd.concat([df_main_src, df_pr], ignore_index=True, sort=False)
    else:
        df_all = df_main_src
    if not df_all.empty:
        df_all.sort_values(by=['date', 'start_time_obj'], inplace=True)

    # Skala pionowa
    PX_PER_MIN = HOUR_HEIGHT_PX / 60.0

    # Zakładki dni (Pon–Pt)
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz"]
    visible_offsets = [0, 1, 2, 3, 4]
    day_tabs = st.columns(len(visible_offsets))
    for i, off in enumerate(visible_offsets):
        current_day_date = week_start + timedelta(days=off)
        if day_tabs[i].button(f"{days_of_week_pl[off]} {current_day_date.day}", use_container_width=True):
            st.session_state.selected_day_index = off
            st.rerun()

    # Dane dnia
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_index)
    day_events = df_all[df_all['date'].dt.date == selected_day_date]
    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    # ---- OŚ CZASU + PŁÓTNO KALENDARZA ----
    base_start, base_end = dtime(7, 0), dtime(21, 0)
    base_start_m, base_end_m = to_minutes(base_start), to_minutes(base_end)

    if not day_events.empty and COMPACT_RANGE:
        ev_start_m = min(day_events['start_time_obj'].dropna().map(to_minutes))
        ev_end_m   = max(day_events['end_time_obj'].dropna().map(to_minutes))
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
    height_px = duration * PX_PER_MIN

    # Godzinowe ticki (lewa szyna)
    first_tick_h = math.ceil(start_m / 60)
    last_tick_h  = math.floor(end_m / 60)
    ticks_html = []
    for h in range(first_tick_h, last_tick_h + 1):
        top = (h * 60 - start_m) * PX_PER_MIN
        ticks_html.append(f"<div class='tick' style='top:{top:.2f}px'></div>")
        ticks_html.append(f"<div class='tick-label' style='top:{top:.2f}px'>{h:02d}:00</div>")

    # Eventy do rysowania
    events = []
    for _, e in day_events.iterrows():
        if pd.isna(e['start_time_obj']) or pd.isna(e['end_time_obj']):
            continue
        events.append({
            "start_min": to_minutes(e['start_time_obj']),
            "end_min": to_minutes(e['end_time_obj']),
            "subject": e.get("subject",""),
            "instructor": e.get("instructor",""),
            "room": e.get("room",""),
            "group": e.get("group",""),
            "start_str": e.get("start_time",""),
            "end_str": e.get("end_time",""),
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
            cluster_cols[c_id] = max(1, peak)
            for idx, *_ in items:
                result[idx]["cluster_id"] = c_id
        return result, cluster_cols

    positioned, cluster_cols = assign_columns_and_clusters_local(events)

    # Render eventów
    events_html_parts = []
    for ev in positioned:
        total_cols = max(1, cluster_cols.get(ev["cluster_id"], 1))
        width_pct = 100 / total_cols
        left_pct = ev["col"] * width_pct
        top = (ev["start_min"] - start_m) * PX_PER_MIN
        height = max(34, (ev["end_min"] - ev["start_min"]) * PX_PER_MIN)
        part = (
            f"<div class='event' style='top:{top:.2f}px;height:{height:.2f}px;"
            f"left:calc({left_pct}% + 2px);width:calc({width_pct}% - 6px);'>"
            f"<div class='title'>{ev['subject']}</div>"
            f"<div class='meta'>{ev['start_str']}–{ev['end_str']} • Sala {ev['room']} • Gr {ev['group']}<br>{ev['instructor']}</div>"
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

except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
