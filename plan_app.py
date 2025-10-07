import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
import math

# --- Konfiguracja strony ---
st.set_page_config(page_title="Interaktywny Plan Zajęć", page_icon="📅", layout="centered")

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

    df_cleaned = df[['date', 'day_of_week', 'start_time', 'end_time', 'subject', 'type', 'degree', 'first_name', 'last_name', 'room', 'group']].copy()
    df_cleaned.dropna(subset=['date'], inplace=True)
    df_cleaned['date'] = pd.to_datetime(df_cleaned['date'], errors='coerce')
    df_cleaned.dropna(subset=['date'], inplace=True)

    df_cleaned['instructor'] = (df_cleaned['degree'].fillna('') + ' ' + df_cleaned['first_name'].fillna('') + ' ' + df_cleaned['last_name'].fillna('')).str.strip()
    df_cleaned['group'] = df_cleaned['group'].fillna('---').astype(str)
    
    # Zachowujemy zarówno obiekty czasu, jak i wersje tekstowe HH:MM
    df_cleaned['start_time_obj'] = pd.to_datetime(df_cleaned['start_time'], format='%H:%M:%S', errors='coerce').dt.time
    df_cleaned['end_time_obj']   = pd.to_datetime(df_cleaned['end_time'],   format='%H:%M:%S', errors='coerce').dt.time
    df_cleaned['start_time'] = df_cleaned['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')
    df_cleaned['end_time']   = df_cleaned['end_time_obj'].apply(  lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')

    df_cleaned.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df_cleaned

# --- Style CSS ---
st.markdown("""
<style>
    /* Layout */
    .stApp > header { background-color: transparent; }
    .main .block-container { padding: 1rem 1rem 5rem 1rem; }
    h1 { text-align: center; color: #1a202c; margin-bottom: 2rem; }

    /* Karta zajęć */
    .class-card { display: flex; gap: 1rem; padding: 1rem 0; border-bottom: 1px solid #f1f3f5; }
    .class-time { font-weight: 600; color: #1a202c; width: 100px; }
    .class-content { flex-grow: 1; }
    .class-subject { font-weight: 600; color: #2d3748; margin-bottom: 0.25rem; }
    .class-details { font-size: 0.9em; color: #718096; }

    /* Oś czasu dnia */
    .timeline-wrapper { position: relative; margin: 0.5rem 0 1rem 0; }
    .timeline { position: relative; border-left: 2px solid #e2e8f0; width: 100%; }
    .tick { position: absolute; left: -2px; right: 0; border-top: 1px dashed #e2e8f0; }
    .tick-label { position: absolute; left: -64px; width: 56px; text-align: right; font-size: 0.8rem; color: #a0aec0; transform: translateY(-50%); }
    .now-line { position: absolute; left: -2px; right: 0; border-top: 2px solid #ef4444; }
    .now-dot { position: absolute; left: -7px; width: 10px; height: 10px; background: #ef4444; border-radius: 9999px; transform: translateY(-50%); }
    .now-badge { position: absolute; right: 0; font-size: 0.75rem; color: #ef4444; transform: translateY(-100%); }
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

    # --- Nawigacja tygodniowa (z przyciskiem DZISIAJ) ---
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
    nav_cols[2].markdown(f"<h2 style='text-align:center'>{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}</h2>", unsafe_allow_html=True)
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

    # --- Oś czasu z poziomą linią „teraz” ---
    # Zakładany zakres dnia (min. 07:00–20:00), rozszerzany o realne zajęcia
    def to_minutes(t: dtime) -> int:
        return t.hour * 60 + t.minute

    base_start = dtime(7, 0)
    base_end   = dtime(20, 0)
    if not day_events.empty:
        ev_min = day_events['start_time_obj'].dropna()
        ev_max = day_events['end_time_obj'].dropna()
        start_t = min([base_start] + ([ev_min.min()] if not ev_min.empty else []))
        end_t   = max([base_end]   + ([ev_max.max()] if not ev_max.empty else []))
    else:
        start_t, end_t = base_start, base_end

    start_m = to_minutes(start_t)
    end_m = to_minutes(end_t)
    duration = max(60, end_m - start_m)  # co najmniej godzina
    PX_PER_MIN = 1  # 1px na minutę => 13h ≈ 780px
    height_px = duration * PX_PER_MIN

    # Godzinowe „kreski”
    first_tick_h = math.ceil(start_m / 60)
    last_tick_h = math.floor(end_m / 60)
    ticks_html = []
    for h in range(first_tick_h, last_tick_h + 1):
        top = (h * 60 - start_m) * PX_PER_MIN
        ticks_html.append(f"<div class='tick' style='top:{top}px'></div>")
        ticks_html.append(f"<div class='tick-label' style='top:{top}px'>{h:02d}:00</div>")

    # Linia „teraz” tylko dla dzisiejszej daty
    now_html = ""
    if selected_day_date == today:
        now_dt = datetime.now()
        now_m = now_dt.hour * 60 + now_dt.minute
        top_now = (now_m - start_m) * PX_PER_MIN
        # ograniczenie do obszaru osi
        top_now = max(0, min(height_px, top_now))
        now_html = (
            f"<div class='now-line' style='top:{top_now}px'></div>"
            f"<div class='now-dot' style='top:{top_now}px'></div>"
            f"<div class='now-badge' style='top:{top_now}px'>Teraz {now_dt.strftime('%H:%M')}</div>"
        )

    timeline_html = f"""
    <div class="timeline-wrapper">
        <div class="timeline" style="height:{height_px}px">
            {''.join(ticks_html)}
            {now_html}
        </div>
    </div>
    """
    st.markdown(timeline_html, unsafe_allow_html=True)

    # --- Lista zajęć dla dnia ---
    if not day_events.empty:
        for _, event in day_events.iterrows():
            st.markdown(f"""
            <div class="class-card">
                <div class="class-time">{event['start_time']}–{event['end_time']}</div>
                <div class="class-content">
                    <div class="class-subject">{event['subject']}</div>
                    <div class="class-details">
                        <span>{event['instructor']}</span> &bull; 
                        <span>Sala: {event['room']}</span> &bull; 
                        <span>Gr: {event['group']}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Brak zajęć w tym dniu.")

except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
