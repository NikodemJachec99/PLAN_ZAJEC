import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

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
    
    df_cleaned['start_time_obj'] = pd.to_datetime(df_cleaned['start_time'], format='%H:%M:%S', errors='coerce').dt.time
    df_cleaned['start_time'] = df_cleaned['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')
    df_cleaned['end_time'] = pd.to_datetime(df_cleaned['end_time'], format='%H:%M:%S', errors='coerce').dt.time.apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')

    df_cleaned.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df_cleaned

# --- Style CSS dla interfejsu z zakładkami ---
st.markdown("""
<style>
    /* Ukrycie domyślnego nagłówka Streamlit */
    .stApp > header { background-color: transparent; }
    .main .block-container { padding: 1rem 1rem 5rem 1rem; }
    h1 { text-align: center; color: #1a202c; margin-bottom: 2rem; }

    /* Nawigacja tygodniowa */
    .week-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
    }
    .week-nav h2 {
        margin: 0;
        font-size: 1.5rem;
        color: #2d3748;
        font-weight: 600;
        text-align: center;
    }
    /* Zakładki dni */
    .day-tabs {
        display: flex;
        justify-content: space-around;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    .day-tab {
        padding: 0.75rem 0.5rem;
        cursor: pointer;
        text-align: center;
        border-bottom: 3px solid transparent;
        flex-grow: 1;
    }
    .day-tab.active {
        border-bottom-color: #2563eb;
    }
    .day-tab.today .day-name {
        color: #2563eb;
        font-weight: 700;
    }
    .day-name { font-weight: 600; color: #4a5568; }
    .day-date { font-size: 0.8rem; color: #a0aec0; }
    
    /* Karta zajęć */
    .class-card {
        display: flex; gap: 1rem; padding: 1rem 0;
        border-bottom: 1px solid #f1f3f5;
    }
    .class-time { font-weight: 600; color: #1a202c; width: 100px; }
    .class-content { flex-grow: 1; }
    .class-subject { font-weight: 600; color: #2d3748; margin-bottom: 0.25rem; }
    .class-details { font-size: 0.9em; color: #718096; }
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

    # --- Nawigacja tygodniowa ---
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=6)
    
    nav_cols = st.columns([1, 4, 1])
    if nav_cols[0].button("⬅️ Poprzedni", use_container_width=True):
        st.session_state.current_week_start -= timedelta(days=7)
        st.rerun()
    if nav_cols[2].button("Następny ➡️", use_container_width=True):
        st.session_state.current_week_start += timedelta(days=7)
        st.rerun()
    nav_cols[1].markdown(f"<h2>{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}</h2>", unsafe_allow_html=True)
    
    # --- Zakładki Dni ---
    days_of_week_pl = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Niedz"]
    day_tabs = st.columns(7)
    for i in range(7):
        current_day_date = week_start + timedelta(days=i)
        is_active = (st.session_state.selected_day_index == i)
        is_today = (current_day_date == today)
        
        active_class = "active" if is_active else ""
        today_class = "today" if is_today else ""

        if day_tabs[i].button(f"{days_of_week_pl[i]} {current_day_date.day}", use_container_width=True):
             st.session_state.selected_day_index = i
             st.rerun()

    # --- Wyświetlanie planu dla wybranego dnia ---
    selected_day_date = week_start + timedelta(days=st.session_state.selected_day_index)
    day_events = df[df['date'].dt.date == selected_day_date]

    st.markdown(f"### {selected_day_date.strftime('%A, %d.%m.%Y')}")

    if not day_events.empty:
        for _, event in day_events.iterrows():
            st.markdown(f"""
            <div class="class-card">
                <div class="class-time">{event['start_time']}</div>
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
