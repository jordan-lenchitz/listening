use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    widgets::{Block, Borders, Paragraph, List, ListItem},
    Terminal, Frame,
};
use std::io;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use listening_tracker::tracking::track::VoiceTrack;

pub struct TuiState {
    pub active_tracks: Vec<VoiceTrack>,
    pub formants: Vec<f64>,
    pub ji_advice: Vec<(usize, String, f64)>, // (track_id, label, cents)
}

pub fn run_tui() -> Result<(), io::Error> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // This is just a skeleton, in a real app we'd have a loop and 
    // receive data from a channel.
    
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    Ok(())
}

pub fn draw_ui(f: &mut Frame, state: &TuiState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage(60),
            Constraint::Percentage(40),
        ])
        .split(f.size());

    // Tracks Block
    let tracks: Vec<ListItem> = state.active_tracks.iter().map(|t| {
        let pitch = t.pitches.last().cloned().unwrap_or(0.0);
        let conf = t.confidences.last().cloned().unwrap_or(0.0);
        ListItem::new(format!("ID: {} | Pitch: {:.1} Hz | Conf: {:.2} | {:?}", t.id, pitch, conf, t.state))
    }).collect();

    let tracks_list = List::new(tracks)
        .block(Block::default().borders(Borders::ALL).title("Active Tracks"));
    f.render_widget(tracks_list, chunks[0]);

    // Analysis Block
    let analysis_layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(50),
            Constraint::Percentage(50),
        ])
        .split(chunks[1]);

    // Formants
    let formants_text = format!("Formants (F1-F4):\n{}", 
        state.formants.iter().map(|f| format!("{:.1} Hz", f)).collect::<Vec<_>>().join("\n"));
    let formants_para = Paragraph::new(formants_text)
        .block(Block::default().borders(Borders::ALL).title("Formants"));
    f.render_widget(formants_para, analysis_layout[0]);

    // JI Advice
    let ji_text = state.ji_advice.iter()
        .map(|(id, label, cents)| format!("ID {}: {} ({:+.1} cents)", id, label, cents))
        .collect::<Vec<_>>().join("\n");
    let ji_para = Paragraph::new(ji_text)
        .block(Block::default().borders(Borders::ALL).title("Just Intonation Advice"));
    f.render_widget(ji_para, analysis_layout[1]);
}
