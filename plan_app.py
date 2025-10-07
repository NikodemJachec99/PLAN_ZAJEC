import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone, time as dtime
import math
import heapq
import html
from zoneinfo import ZoneInfo

# --- STAŁE DLA GĘSTOŚCI WIDOKU ---
HOUR_HEIGHT_PX = 65      # 1h = 65px. Zmniejsz do 60/55, gdy chcesz jeszcze ciaśniej.
COMPACT_RANGE  = True      # przycinaj widok do zakresu zajęć (+/- 15 min)
TZ_WA = ZoneInfo("Europe/Warsaw")

# --- USTAWIENIA STRONY ---
st.set_page_config(page_title="Plan Zajęć ❤️", page_icon="📅", layout="centered")

# --- AUTO-ODŚWIEŻANIE (60 s) ---
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 1000, key="autorefresh-60s")
except Exception:
    st.markdown("<script>setTimeout(()=>window.location.reload(), 60000);</script>", unsafe_allow_html=True)

# --- WCZYTYWANIE DANYCH ---
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

# --- STYLE ---
st.markdown("""
<style>
  html { font-size: 13.5px; }
  body, .stApp { line-height: 1.25; }
  .stApp > header { background-color: transparent; }
  .main .block-container { padding: 0.45rem 0.55rem 3rem 0.55rem; }
  h1 { text-align:center; color:#1a202c; margin-bottom:0.55rem; font-size:1.28rem; }
  .week-range { text-align:center; font-size:1.0rem; font-weight:600; color:#2d3748; margin:0.15rem 0 0.5rem; }
  .day-layout { display:grid; grid-template-columns:64px 1fr; gap:0.5rem; align-items:start; }
  .timeline-rail { position:sticky; top:0; width:64px; border-right:2px solid #e2e8f0; }
  .timeline-rail-inner { position:relative; height:var(--day-height, 720px); }
  .tick { position:absolute; left:0; right:0; border-top:1px dashed #e2e8f0; }
  .tick-label { position:absolute; left:0; width:54px; text-align:right; font-size:0.68rem; color:#94a3b8; transform:translateY(-50%); padding-right:4px; }
  .calendar-canvas { position:relative; min-height:var(--day-height, 720px); border-left:2px solid #e2e8f0; }
  .event {
    position:absolute; box-sizing:border-box; padding:5px 7px;
    background:#0ea5e910; border:1px solid #38bdf8; border-radius:9px;
    overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.05);
  }
  .event .title { font-weight:700; color:#0f172a; margin-bottom:1px; font-size:0.9rem; }
  .event .meta { font-size:.68rem; color:#334155; line-height:1.12; }
  .now-line-wide { position:absolute; left:0; right:0; border-top:2px solid #ef4444; z-index:3; }
  .now-badge { position:absolute; right:6px; transform:translateY(-100%); font-size:.66rem; color:#ef4444; z-index:4; background:transparent; }
  @media (max-width: 640px) {
    html { font-size: 12.8px; }
    .day-layout { grid-template-columns:52px 1fr; gap:0.4rem; }
    .timeline-rail { width:52px; }
    .tick-label { width:46px; font-size:.64rem; }
    .event { padding:4px 6px; border-radius:8px; }
    .event .title { font-size:.86rem; }
    .event .meta { font-size:.64rem; }
  }
</style>
""", unsafe_allow_html=True)

# --- POMOCNICZE ---
def to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute

# --- APLIKACJA ---
try:
    df = load_data("plan_zajec.xlsx")
    st.title("Plan Zajęć ❤️")

    # --- NOWA FUNKCJA: Checkbox do filtrowania grup ---
    filter_magdalenka = st.checkbox("Grupy Magdalenki")

    # Czas Warszawy
    now_dt = datetime.now(timezone.utc).astimezone(TZ_WA)
    today = now_dt.date()

    # Stan sesji
    if 'current_week_start' not in st.session_state:
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
    if 'selected_day_offset' not in st.session_state:
        st.session_state.selected_day_offset = min(today.weekday(), 4)

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

    # Skala pionowa
    PX_PER_MIN = HOUR_HEIGHT_PX / 60.0

    # Zakładki dni (Pon–Pt)
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt"]
    visible_offsets = [0, 1, 2, 3, 4]
    day_tabs = st.columns(len(visible_offsets))
    for i, off in enumerate(visible_offsets):
        current_day_date = week_start + timedelta(days=off)
        if day_tabs[i].button(f"{days_of_week_pl[off]} {current_day_date.day}", use_container_width=True, type=("primary" if st.session_state.selected_day_offset == off else "secondary")):
            st.session_state.selected_day_offset = off
            st.rerun()

    # Dane dnia
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_offset)
    day_events = df[df['date'].dt.date == selected_day_date]

    # --- NOWA FUNKCJA: Logika filtrowania ---
    if filter_magdalenka:
        # Zostawiamy tylko zajęcia dla grupy '1' lub 'd'
        day_events = day_events[day_events['group'].isin(['11', 'd'])]

    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    # ---- OŚ CZASU + PŁÓTNO KALENDARZA ----
    base_start, base_end = dtime(7, 0), dtime(21, 0)
    base_start_m, base_end_m = to_minutes(base_start), to_minutes(base_end)

    if not day_events.empty and COMPACT_RANGE:
        ev_start_m = min(day_events['start_time_obj'].dropna().map(to_minutes))
        ev_end_m   = max(day_events['end_time_obj'].dropna().map(to_minutes))
        start_m = max(base_start_m, int(math.floor((ev_start_m - 15) / 60) * 60))
        end_m   = min(base_end_m,   int(math.ceil((ev_end_m + 15) / 60) * 60))
    else:
        start_m, end_m = base_start_m, base_end_m
        if not day_events.empty:
            ev_min = day_events['start_time_obj'].dropna()
            ev_max = day_events['end_time_obj'].dropna()
            start_m = min([base_start_m] + ([min(map(to_minutes, ev_min))] if len(ev_min) else []))
            end_m   = max([base_end_m]   + ([max(map(to_minutes, ev_max))] if len(ev_max) else []))

    duration = max(60, end_m - start_m)
    height_px = duration * PX_PER_MIN

    # Godzinowe ticki
    ticks_html = []
    first_tick_h = math.ceil(start_m / 60)
    last_tick_h  = math.floor(end_m / 60)
    for h in range(first_tick_h, last_tick_h + 1):
        top = (h * 60 - start_m) * PX_PER_MIN
        ticks_html.append(f"<div class='tick' style='top:{top:.2f}px'></div>")
        ticks_html.append(f"<div class='tick-label' style='top:{top:.2f}px'>{h:02d}:00</div>")

    # Eventy źródłowe
    events = []
    for _, e in day_events.iterrows():
        if pd.isna(e['start_time_obj']) or pd.isna(e['end_time_obj']): continue
        events.append({
            "start_min": to_minutes(e['start_time_obj']), "end_min": to_minutes(e['end_time_obj']),
            "subject": e["subject"], "instructor": e["instructor"], "room": e["room"], "group": e["group"],
            "start_str": e["start_time"], "end_str": e["end_time"]
        })
    events.sort(key=lambda x: (x["start_min"], x["end_min"]))

    # Reszta kodu bez zmian...
    # (Algorytm kolumn, renderowanie eventów, linia TERAZ, składanie layoutu)
    
    # Kolumny + klastry
    # (Ten skomplikowany fragment jest skopiowany z Twojej wersji i pozostawiony bez zmian)
    result = []
    active = []
    free_cols = []
    next_col = 0
    clusters, current_cluster = [], []
    for idx, ev in enumerate(events):
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
    positioned = result

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
            f"<div class='title'>{html.escape(ev['subject'])}</div>"
            f"<div class='meta'>{ev['start_str']}–{ev['end_str']} • Sala {html.escape(ev['room'])} • Gr {html.escape(ev['group'])}<br>{html.escape(ev['instructor'])}</div>"
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

