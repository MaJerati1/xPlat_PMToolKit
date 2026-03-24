'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { Calendar, Loader2, Check, Users, Clock, ExternalLink, Link2, AlertCircle, Download, ChevronRight } from 'lucide-react';

export default function CalendarPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [authUrl, setAuthUrl] = useState(null);
  const [importing, setImporting] = useState(null);
  const [imported, setImported] = useState({});
  const [error, setError] = useState(null);
  const [daysAhead, setDaysAhead] = useState(14);

  useEffect(() => { loadEvents(); }, [daysAhead]);

  const loadEvents = async () => {
    setLoading(true); setError(null);
    try {
      const data = await api.getCalendarEvents(daysAhead);
      setEvents(data.events || []);
      setConnected(data.connected !== false);
      if (!data.connected) {
        const auth = await api.getGoogleAuthUrl();
        setAuthUrl(auth.auth_url);
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleImport = async (eventId, title) => {
    setImporting(eventId);
    try {
      const result = await api.importCalendarEvent(eventId);
      setImported(prev => ({ ...prev, [eventId]: result }));
    } catch (e) {
      if (e.message?.includes('already been imported')) {
        setImported(prev => ({ ...prev, [eventId]: { already: true } }));
      } else {
        setError(`Import failed: ${e.message}`);
      }
    } finally { setImporting(null); }
  };

  return (
    <><Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Calendar Import</h1>
          <p className="text-sm text-txtsec">Import upcoming events from Google Calendar into the Meeting Toolkit.</p>
        </div>

        {!connected && !loading && (
          <div className="bg-bgcard rounded-xl border border-bdr shadow-sm p-8 text-center mb-6">
            <Calendar className="w-10 h-10 text-txttri mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-txt mb-2">Connect Google Calendar</h3>
            <p className="text-sm text-txtsec mb-5 max-w-md mx-auto">Link your Google account to import meetings, attendees, and agenda items automatically.</p>
            {authUrl ? (
              <a href={authUrl} className="px-6 py-3 bg-acc text-white rounded-xl font-semibold text-sm hover:bg-acchov transition-all inline-flex items-center gap-2">
                <Calendar className="w-4 h-4" /> Connect Google Calendar
              </a>
            ) : (
              <p className="text-xs text-txttri">Configure Google OAuth credentials in Getting Started first.</p>
            )}
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
          </div>
        )}

        {connected && (
          <>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-txttri">Showing next</span>
                <select value={daysAhead} onChange={e => setDaysAhead(Number(e.target.value))}
                  className="px-2 py-1 bg-bgcard border border-bdr rounded-lg text-sm text-txt">
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                </select>
              </div>
              <button onClick={loadEvents} disabled={loading}
                className="px-3 py-1.5 bg-bgcard border border-bdr rounded-lg text-xs font-medium text-txtsec hover:text-txt transition-all">
                {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Refresh'}
              </button>
            </div>

            {loading ? (
              <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 text-acc animate-spin" /></div>
            ) : events.length === 0 ? (
              <div className="bg-bgcard rounded-xl border border-bdr p-12 text-center">
                <Calendar className="w-8 h-8 text-txttri mx-auto mb-3" />
                <p className="text-sm text-txtsec">No upcoming events found in the next {daysAhead} days.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {events.map(event => {
                  const imp = imported[event.google_event_id];
                  return (
                    <div key={event.google_event_id} className="bg-bgcard rounded-xl border border-bdr shadow-sm p-5 hover:shadow-md transition-shadow">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-txt mb-1">{event.title}</h3>
                          <div className="flex items-center gap-3 text-xs text-txtsec flex-wrap">
                            {event.date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {event.date}</span>}
                            {event.time && <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {event.time.slice(0,5)}</span>}
                            {event.duration_minutes && <span>{event.duration_minutes} min</span>}
                            {event.attendee_count > 0 && <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {event.attendee_count}</span>}
                            {event.meeting_link && <span className="flex items-center gap-1"><Link2 className="w-3 h-3" /> Meeting link</span>}
                          </div>
                          {event.agenda_items?.length > 0 && (
                            <div className="mt-2 text-xs text-txttri">
                              {event.agenda_items.length} agenda item(s): {event.agenda_items.slice(0,2).map(a => a.title).join(', ')}{event.agenda_items.length > 2 ? '...' : ''}
                            </div>
                          )}
                        </div>
                        <div className="flex-shrink-0">
                          {imp?.meeting_id ? (
                            <a href={`/analyze?meeting=${imp.meeting_id}`}
                              className="px-3 py-1.5 bg-grnsoft text-grn rounded-lg text-xs font-semibold inline-flex items-center gap-1.5">
                              <Check className="w-3 h-3" /> Imported <ChevronRight className="w-3 h-3" />
                            </a>
                          ) : imp?.already ? (
                            <span className="px-3 py-1.5 bg-bgelev text-txtsec rounded-lg text-xs font-medium">Already imported</span>
                          ) : (
                            <button onClick={() => handleImport(event.google_event_id, event.title)}
                              disabled={importing === event.google_event_id}
                              className="px-4 py-1.5 bg-acc text-white rounded-lg text-xs font-semibold hover:bg-acchov transition-all inline-flex items-center gap-1.5 disabled:opacity-50">
                              {importing === event.google_event_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                              Import
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
