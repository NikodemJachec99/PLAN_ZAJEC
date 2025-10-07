import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import math
import heapq
import pytz
from datetime import datetime
from zoneinfo import ZoneInfo

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
  .stApp > header { background-color: transparent; }
  .main .block-container { padding: 1rem 1rem 5rem 1rem; }
  h1 { text-align:center; color:#1a202c; margin-bottom:1.0rem; }
  .week-range { text-align:center; font-size:1.25rem; font-weight:600; color:#2d3748; margin:0.25rem 0 0.75rem; }
  .day-layout { display:grid; grid-template-columns:88px 1fr; gap:1rem; align-items:start; }

  /* Oś godzin */
  .timeline-rail { position:sticky; top:0; width:88px; border-right:2px solid #e2e8f0; }
  .timeline-rail-inner { position:relative; height:var(--day-height, 960px); }
  .tick { position:absolute; left:0; right:0; border-top:1px dashed #e2e8f0; }
  .tick-label { position:absolute; left:0; width:76px; text-align:right; font-size:0.8rem; color:#a0aec0; transform:translateY(-50%); padding-right:6px; }

  /* Płótno i eventy */
  .calendar-canvas { position:relative; min-height:var(--day-height, 960px); border-left:2px solid #e2e8f0; }
  .event { position:absolute; box-sizing:border-box; padding:10px 12px; background:#0ea5e912; border:1px solid #38bdf8; border-radius:12px;
           overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.06); }
  .event .title { font-weight:700; color:#0f172a; margin-bottom:2px; }
  .event .meta { font-size:.85rem; color:#334155; line-height:1.2; }

  .now-line-wide { position:absolute; left:0; right:0; border-top:2px solid #ef4444; z-index:3; }
  .now-badge { position:absolute; right:6px; transform:translateY(-100%); font-size:.75rem; color:#ef4444; z-index:4; background:transparent; }
</style>
""", unsafe_allow_html=True)

# --- POMOCNICZE ---
def to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute

def assign_columns_and_clusters(evts):
    """Nadaje kolumny i identyfikuje klastry (ciągi nakładających się eventów)."""
    result = []
    active = []        # min-heap po end_min: (end_min, col, idx)
    free_cols = []     # min-heap z wolnymi numerami kolumn
    next_col = 0
    clusters, current_cluster = [], []

    for idx, ev in enumerate(evts):
        while active and active[0][0] <= ev["start_min"]:
            _, col_finished, _ = heapq.heappop(active)
            heapq.heappush(free_cols, col_finished)

        if not active and current_cluster:
            clusters.append(current_cluster)
            current_cluster = []

        if free_cols:
            col = heapq.heappop(free_cols)
        else:
            col = next_col
            next_col += 1

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
    df = load_data("plan_zajec.xlsx")
    st.title("Plan Zajęć ❤️")

now_dt = datetime.now(ZoneInfo("Europe/Warsaw"))
today = now_dt.date()

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

    # 🔎 Skala wysokości 1 godziny (60–220 px); zapamiętujemy w sesji:
    if 'hour_height' not in st.session_state:
        st.session_state.hour_height = 120
    st.session_state.hour_height = st.slider("Wysokość 1h (px)", 60, 220, st.session_state.hour_height, step=10, help="Zwiększ, jeśli treść zajęć się nie mieści")
    PX_PER_MIN = st.session_state.hour_height / 60.0  # skala pionowa

    # Zakładki dni
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz"]
    day_tabs = st.columns(7)
    for i in range(7):
        current_day_date = week_start + timedelta(days=i)
        if day_tabs[i].button(f"{days_of_week_pl[i]} {current_day_date.day}", use_container_width=True):
            st.session_state.selected_day_index = i
            st.rerun()

    # Dane dnia
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_index)
    day_events = df[df['date'].dt.date == selected_day_date]
    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    # ---- OŚ CZASU + PŁÓTNO KALENDARZA ----
    base_start, base_end = dtime(7, 0), dtime(21, 0)

    if not day_events.empty:
        ev_min = day_events['start_time_obj'].dropna()
        ev_max = day_events['end_time_obj'].dropna()
        start_t = min([base_start] + ([ev_min.min()] if not ev_min.empty else []))
        end_t   = max([base_end]   + ([ev_max.max()] if not ev_max.empty else []))
    else:
        start_t, end_t = base_start, base_end

    start_m, end_m = to_minutes(start_t), to_minutes(end_t)
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

    # Eventy źródłowe
    events = []
    for _, e in day_events.iterrows():
        if pd.isna(e['start_time_obj']) or pd.isna(e['end_time_obj']):
            continue
        events.append({
            "start_min": to_minutes(e['start_time_obj']),
            "end_min": to_minutes(e['end_time_obj']),
            "subject": e["subject"],
            "instructor": e["instructor"],
            "room": e["room"],
            "group": e["group"],
            "start_str": e["start_time"],
            "end_str": e["end_time"]
        })
    events.sort(key=lambda x: (x["start_min"], x["end_min"]))

    # Kolumny + klastry (równoległe obok siebie)
    positioned, cluster_cols = assign_columns_and_clusters(events)

    # Render eventów (jednolinijkowe <div>)
    events_html_parts = []
    for ev in positioned:
        total_cols = max(1, cluster_cols.get(ev["cluster_id"], 1))
        width_pct = 100 / total_cols
        left_pct = ev["col"] * width_pct
        top = (ev["start_min"] - start_m) * PX_PER_MIN
        height = max(48, (ev["end_min"] - ev["start_min"]) * PX_PER_MIN)  # podniosłem min-wys na 48px
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
        now_dt = datetime.now()
        now_m = now_dt.hour * 60 + now_dt.minute
        top_now = max(0, min(height_px, (now_m - start_m) * PX_PER_MIN))
        now_wide_html = (
            f"<div class='now-line-wide' style='top:{top_now:.2f}px'></div>"
            f"<div class='now-badge' style='top:{top_now:.2f}px'>Teraz {now_dt.strftime('%H:%M')}</div>"
        )

    # Layout
    day_layout_html = (
        f"<div class='day-layout' style='--day-height:{height_px:.2f}px'>"
        f"<div class='timeline-rail'><div class='timeline-rail-inner' style='height:{height_px:.2f}px'>{''.join(ticks_html)}</div></div>"
        f"<div class='calendar-canvas' style='min-height:{height_px:.2f}px'>{now_wide_html}{events_html if events_html else '<div style=\"padding:12px;color:#64748b;\">Brak zajęć</div>'}</div>"
        f"</div>"
    )
    st.markdown(day_layout_html, unsafe_allow_html=True)

except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
st.markdown("---")
st.write("Made with ❤️ for you!")




