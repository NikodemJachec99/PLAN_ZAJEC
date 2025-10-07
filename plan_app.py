import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# --- Konfiguracja strony ---
st.set_page_config(page_title="Interaktywny Plan Zajęć", page_icon="📅", layout="wide")

# --- Wczytywanie i przetwarzanie danych ---
@st.cache_data(ttl=600) # Odśwież dane co 10 minut
def load_data(file_path):
    """Wczytuje i przetwarza dane z pliku Excel."""
    df = pd.read_excel(file_path, header=3)
    
    # Czyszczenie i formatowanie
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
    
    # Konwersja czasu na obiekty time dla łatwiejszych obliczeń
    df_cleaned['start_time_obj'] = pd.to_datetime(df_cleaned['start_time'], format='%H:%M:%S', errors='coerce').dt.time
    df_cleaned['end_time_obj'] = pd.to_datetime(df_cleaned['end_time'], format='%H:%M:%S', errors='coerce').dt.time
    
    # Formatowanie czasu do wyświetlania
    df_cleaned['start_time'] = df_cleaned['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')
    df_cleaned['end_time'] = df_cleaned['end_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')

    df_cleaned.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df_cleaned

# --- Style CSS ---
st.markdown("""
<style>
    /* Nawigacja */
    .nav-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #f8f9fa;
        padding: 10px 20px;
        border-radius: 12px;
        margin-bottom: 2rem;
        border: 1px solid #dee2e6;
    }
    .nav-container h2 {
        margin: 0;
        font-size: 1.75rem;
        color: #2c3e50;
    }
    .week-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 1.5rem;
    }
    /* Karta dnia */
    .day-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #dee2e6;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        min-height: 400px;
        position: relative; /* Potrzebne dla linii czasu */
    }
    .day-card.today {
        border: 2px solid #007bff;
        box-shadow: 0 8px 24px rgba(0,123,255,0.1);
    }
    .day-header {
        margin-bottom: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #f1f3f5;
    }
    .day-header h3 {
        margin: 0;
        color: #2c3e50;
        font-size: 1.25rem;
    }
    .day-header span {
        color: #6c757d;
        font-size: 0.9rem;
    }
    /* Karta zajęć */
    .class-card {
        border-left: 4px solid #007bff;
        padding: 0.8rem 1rem;
        margin-bottom: 1rem;
        background-color: #f8f9fa;
        border-radius: 6px;
    }
    .class-time { font-weight: 600; color: #343a40; }
    .class-subject { font-weight: 500; font-size: 1.05em; margin: 5px 0; }
    .class-details { font-size: 0.85em; color: #6c757d; }
    /* Linia czasu */
    .timeline {
        position: absolute;
        left: 0;
        right: 0;
        height: 2px;
        background-color: red;
        z-index: 10;
    }
    .timeline::before {
        content: '';
        position: absolute;
        left: -5px;
        top: -4px;
        width: 10px;
        height: 10px;
        background-color: red;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)

# --- Logika aplikacji ---
try:
    df = load_data("PI_s_II_26_09_2025 (1).xlsx")

    # Inicjalizacja stanu sesji
    if 'current_week_start' not in st.session_state:
        today = datetime.now().date()
        # Początek tygodnia to poniedziałek
        st.session_state.current_week_start = today - timedelta(days=today.weekday())

    # --- Nawigacja ---
    nav_cols = st.columns([1, 4, 1, 1])
    with nav_cols[0]:
        if st.button("⬅️ Poprzedni", use_container_width=True):
            st.session_state.current_week_start -= timedelta(days=7)
    with nav_cols[2]:
        if st.button("Następny ➡️", use_container_width=True):
            st.session_state.current_week_start += timedelta(days=7)
    with nav_cols[3]:
        if st.button("🗓️ Dzisiaj", use_container_width=True):
            today = datetime.now().date()
            st.session_state.current_week_start = today - timedelta(days=today.weekday())
    
    # Wyświetlanie daty
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=6)
    with nav_cols[1]:
        st.markdown(f"<div class='nav-container'><h2>{week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')}</h2></div>", unsafe_allow_html=True)


    # --- Wyświetlanie tygodnia ---
    st.markdown('<div class="week-grid">', unsafe_allow_html=True)
    
    today_date = datetime.now().date()
    current_time = datetime.now().time()
    
    days_of_week_pl = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        day_events = df[df['date'].dt.date == current_day]
        
        is_today_class = "today" if current_day == today_date else ""
        
        with st.container():
            st.markdown(f'<div class="day-card {is_today_class}">', unsafe_allow_html=True)
            
            # Nagłówek dnia
            st.markdown(f"""
            <div class="day-header">
                <h3>{days_of_week_pl[i]}</h3>
                <span>{current_day.strftime('%d.%m.%Y')}</span>
            </div>
            """, unsafe_allow_html=True)

            # Linia czasu (jeśli to dzisiejszy dzień)
            if current_day == today_date:
                # Oblicz pozycję procentową linii czasu (zakładamy dzień od 8:00 do 20:00)
                day_start_hour = 8
                day_end_hour = 20
                total_minutes_in_day = (day_end_hour - day_start_hour) * 60
                minutes_from_start = (current_time.hour - day_start_hour) * 60 + current_time.minute
                
                if 0 <= minutes_from_start <= total_minutes_in_day:
                    top_percentage = (minutes_from_start / total_minutes_in_day) * 100
                    st.markdown(f'<div class="timeline" style="top: {top_percentage}%;"></div>', unsafe_allow_html=True)

            # Wyświetlanie zajęć
            if not day_events.empty:
                for _, event in day_events.iterrows():
                    st.markdown(f"""
                    <div class="class-card">
                        <div class="class-time">{event['start_time']} - {event['end_time']}</div>
                        <div class="class-subject">{event['subject']}</div>
                        <div class="class-details">
                            <span>{event['instructor']}</span> | 
                            <span>{event['room']}</span> | 
                            <span>{event['group']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<p style='color: #adb5bd; text-align: center; margin-top: 2rem;'>Brak zajęć</p>", unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium na GitHubie.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")

