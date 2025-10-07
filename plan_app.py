import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import math

# --- Konfiguracja strony ---
st.set_page_config(page_title="Interaktywny Plan Zajęć", page_icon="📅", layout="centered")

# --- Auto-odświeżanie co 60 s ---
# Preferowany sposób (pakiet streamlit_autorefresh), z fallbackiem do JS jeśli niedostępny
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 1000, key="autorefresh-60s")
except Exception:
    st.markdown(
        "<script>setTimeout(()=>window.location.reload(), 60000);</script>",
        unsafe_allow_html=True
    )

# --- Wczytywanie i przetwarzanie danych ---
@st.cache_data(ttl=600)
def load_data(file_path):
    """Wczytuje i przetwarza dane z pliku Excel."""
    df = pd.read_excel(file_path, header=3)

    df.columns = [
        'date', 'day_of_week', 'start_time', 'end_time', 'subject', 'type',
        'degree', 'first_name', 'last_name', 'room', 'field_year', 'group',
        'info_combined', 'additional_info'
    ] + [f'unnamed_{i}' for i in range(len(df.columns) - 14)]

    df_cleaned = df[['date', 'day_of_week', 'start_time', 'end_time', 'subject',
                     'type', 'degree', 'first_name', 'last_name', 'room', 'group']].copy()
    df_cleaned.dropna(subset=['date'], inplace=True)
    df_cleaned['date'] = pd.to_datetime(df_cleaned['date'], errors='coerce')
    df_cleaned.dropna(subset=['date'], inplace=True)

    df_cleaned['instructor'] = (
        df_cleaned['degree'].fillna('') + ' ' +
        df_cleaned['first_name'].fillna('') + ' ' +
        df_cleaned['last_name'].fillna('')
    ).str.strip()
    df_cleaned['group'] = df_cleaned['group'].fillna('---').astype(str)

    # Obiekty czasu + wersje tekstowe
    df_cleaned['start_time_obj'] = pd.to_datetime(
        df_cleaned['start_time'], format='%H:%M:%S', errors='coerce'
    ).dt.time
    df_cleaned['end_time_obj'] = pd.to_datetime(
        df_cleaned['end_time'], format='%H:%M:%S', errors='coerce'
    ).dt.time
    df_cleaned['start_time'] = df_cleaned['start_time_obj'].apply(
        lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd'
    )
    df_cleaned['end_time'] = df_cleaned['end_time_obj'].apply(
        lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd'
    )

    df_cleaned.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df_cleaned

# --- Style CSS ---
st.markdown("""
<style>
  /* Layout ogólny */
  .stApp > header { background-color: transparent; }
  .main .block-container { padding: 1rem 1rem 5rem 1rem; }
  h1 { text-align: center; color: #1a202c; margin-bottom: 2rem; }

  /* Karty zajęć */
  .class-card { display:flex; gap:1rem; padding:1rem 0; border-bottom:1px solid #f1f3f5; }
  .class-time { font-weight:600; color:#1a202c; width:120px; }
  .class-content { flex-grow:1; }
  .class-subject { font-weight:600; color:#2d3748; margin-bottom:0.25rem; }
  .class-details { font-size:0.9em; color:#718096; }

  /* ===== LAYOUT DNIA: oś (lewo) + lista (prawo) ===== */
  .day-layout{ display:grid; grid-template-columns:88px 1fr; gap:1rem; align-items:start; }

  .timeline-rail{ position:sticky; top:0; width:88px; border-right:2px solid #e2e8f0; }
  .timeline-rail-inner{ position:relative; height:var(--day-height, 720px); }

  .tick{ position:absolute; left:0; right:0; border-top:1px dashed #e2e8f0; }
  .tick-label{ position:absolute; left:0; width:76px; text-align:right; font-size:0.8rem; color:#a0aec0; transform:translateY(-50%); padding-right:6px; }

  .now-line{ position:absolute; left:0; right:0; border-top:2px solid #ef4444; }
  .now-dot{ position:absolute; right:-6px; width:10px; height:10px; background:#ef4444; border-radius:9999px; transform:translateY(-50%); }

  .classes{ position:relative; min-height:var(--day-height, 720px); }
  .now-line-wide{ position:absolute; left:0; right:0; border-top:2px solid #ef4444; z-index:2; }

  /* Z-index tak, by linia „Teraz” była nad tłem, lecz nie zasłaniała treści */
  .classes .class-card{ position:relative; z-index:1; background:#fff; }
</style>
""", unsafe_allow_html=True)

# --- Logika Aplikacji ---
try:
    df = load_data("plan_zajec.xlsx")
    st.title("Interaktywny Plan Zajęć")

    # --- Stan sesji ---
    today = datetime.now().date()
    if 'current_week_start' not in st.session_state:
        st.session_state.current_week_start = today - timedelta(days=today.weekday())
    if 'selected_day_index' not in st.session_state:
        st.session_state.selected_day_index = today.weekday()

    # --- Nawigacja tygodniowa (z przyciskiem „Dziś”) ---
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
    nav_cols[2].markdown(
        f"<h2 style='text-align:center'>{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}</h2>",
        unsafe_allow_html=True
    )
    if nav_cols[3].button("Następny ➡️", use_container_width=True):
        st.session_state.current_week_start += timedelta(days=7)
        st.rerun()

    # --- Zakładki Dni ---
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz"]
    day_tabs = st.columns(7)
    for i in range(7):
        current_day_date = week_start + timedelta(days=i)
        if day_tabs[i].button(f"{days_of_week_pl[i]} {current_day_date.day}", use_container_width=True):
            st.session_state.selected_day_index = i
            st.rerun()

    # --- Wybrany dzień i dane ---
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_index)
    day_events = df[df['date'].dt.date == selected_day_date]

    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    # --- Oś czasu i lista zajęć w jednym layoucie (lewa kolumna: oś; prawa: zajęcia) ---
    # Zakres dnia (dynamicznie rozszerzany na podstawie zajęć)
    def to_minutes(t): return t.hour * 60 + t.minute
    base_start, base_end = dtime(7, 0), dtime(20, 0)

    if not day_events.empty:
        ev_min = day_events['start_time_obj'].dropna()
        ev_max = day_events['end_time_obj'].dropna()
        start_t = min([base_start] + ([ev_min.min()] if not ev_min.empty else []))
        end_t = max([base_end] + ([ev_max.max()] if not ev_max.empty else []))
    else:
        start_t, end_t = base_start, base_end

    start_m, end_m = to_minutes(start_t), to_minutes(end_t)
    duration = max(60, end_m - start_m)     # min. godzina
    PX_PER_MIN = 1                           # 1px na minutę (np. 13h ≈ 780px)
    height_px = duration * PX_PER_MIN

    # Godzinowe „kreski”
    first_tick_h = math.ceil(start_m / 60)
    last_tick_h = math.floor(end_m / 60)
    ticks_html = []
    for h in range(first_tick_h, last_tick_h + 1):
        top = (h * 60 - start_m) * PX_PER_MIN
        ticks_html.append(f"<div class='tick' style='top:{top}px'></div>")
        ticks_html.append(f"<div class='tick-label' style='top:{top}px'>{h:02d}:00</div>")

    # Linia „Teraz”
    now_rail_html, now_wide_html = "", ""
    if selected_day_date == today:
        now_dt = datetime.now()
        now_m = now_dt.hour * 60 + now_dt.minute
        top_now = max(0, min(height_px, (now_m - start_m) * PX_PER_MIN))
        now_rail_html = (
            f"<div class='now-line' style='top:{top_now}px'></div>"
            f"<div class='now-dot' style='top:{top_now}px'></div>"
        )
        now_wide_html = f"<div class='now-line-wide' style='top:{top_now}px'></div>"

    # HTML kart zajęć (prawa kolumna)
    if not day_events.empty:
        cards = []
        for _, e in day_events.iterrows():
            cards.append(f"""
            <div class="class-card">
              <div class="class-time">{e['start_time']}–{e['end_time']}</div>
              <div class="class-content">
                <div class="class-subject">{e['subject']}</div>
                <div class="class-details">
                  <span>{e['instructor']}</span> &bull; 
                  <span>Sala: {e['room']}</span> &bull; 
                  <span>Gr: {e['group']}</span>
                </div>
              </div>
            </div>""")
        classes_html = "".join(cards)
    else:
        classes_html = "<div class='class-card'><div class='class-content'><div class='class-subject'>Brak zajęć</div></div></div>"

    day_layout_html = f"""
    <div class="day-layout" style="--day-height:{height_px}px">
      <div class="timeline-rail">
        <div class="timeline-rail-inner" style="height:{height_px}px">
          {''.join(ticks_html)}
          {now_rail_html}
        </div>
      </div>
      <div class="classes" style="min-height:{height_px}px">
        {now_wide_html}
        {classes_html}
      </div>
    </div>
    """
    st.markdown(day_layout_html, unsafe_allow_html=True)

except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
