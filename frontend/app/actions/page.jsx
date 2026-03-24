'use client';
import { useState, useEffect } from 'react';
import Header from '../../components/Header';
import { api } from '../../lib/api';
import { ListChecks, Loader2, Check, X, RotateCcw, Filter, AlertCircle, Clock, User, ChevronDown } from 'lucide-react';

function ActionItemCard({ item, meetingTitle, onConfirm, onDecline, onRestore }) {
  const isDeclined = item.status === 'declined' || item.rejected;
  return (
    <div className={`p-4 rounded-xl border transition-all ${
      isDeclined ? 'border-red/30 bg-redsoft opacity-70'
        : item.confirmed ? 'border-grn/30 bg-grnsoft'
          : 'border-bdr bg-bgcard hover:shadow-sm'
    }`}>
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium text-txt leading-relaxed ${isDeclined ? 'line-through' : ''}`}>{item.task}</p>
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {item.owner_name && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blusoft text-blu">
                <User className="w-3 h-3" /> {item.owner_name}
              </span>
            )}
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
              item.priority === 'high' ? 'bg-redsoft text-red' : item.priority === 'low' ? 'bg-grnsoft text-grn' : 'bg-ambsoft text-amb'
            }`}>{item.priority}</span>
            {item.confirmed && <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-grnsoft text-grn">Confirmed</span>}
            {isDeclined && <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-redsoft text-red">Declined</span>}
            {item.deadline && (
              <span className="inline-flex items-center gap-1 text-xs text-txttri">
                <Clock className="w-3 h-3" /> {item.deadline}
              </span>
            )}
          </div>
          {meetingTitle && <p className="text-xs text-txttri mt-1.5">From: {meetingTitle}</p>}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {!item.confirmed && !isDeclined && (
            <>
              <button onClick={() => onConfirm(item)} title="Confirm" className="p-1.5 rounded-md hover:bg-grnsoft text-grn transition-colors"><Check className="w-4 h-4" /></button>
              <button onClick={() => onDecline(item)} title="Decline" className="p-1.5 rounded-md hover:bg-redsoft text-red transition-colors"><X className="w-4 h-4" /></button>
            </>
          )}
          {isDeclined && (
            <button onClick={() => onRestore(item)} className="px-2.5 py-1 rounded-md border border-bdr bg-bgelev text-xs font-medium text-txtsec hover:text-txt transition-colors">Restore</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ActionsPage() {
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState('all');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterPriority, setFilterPriority] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => {
    loadData();
  }, [selectedMeeting]);

  const loadData = async () => {
    setLoading(true); setError(null);
    try {
      const meetingData = await api.listMeetings(1, 50);
      setMeetings(meetingData.meetings || []);

      if (selectedMeeting === 'all') {
        // Load action items from all meetings
        const allItems = [];
        for (const m of (meetingData.meetings || [])) {
          try {
            const ai = await api.getActionItems(m.id);
            if (Array.isArray(ai)) {
              allItems.push(...ai.map(i => ({ ...i, _meetingTitle: m.title, rejected: false })));
            }
          } catch {}
        }
        setItems(allItems);
      } else {
        const ai = await api.getActionItems(selectedMeeting);
        const m = (meetingData.meetings || []).find(m => m.id === selectedMeeting);
        setItems((Array.isArray(ai) ? ai : []).map(i => ({ ...i, _meetingTitle: m?.title, rejected: false })));
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleConfirm = async (item) => {
    try {
      await api.updateActionItem(item.id, { confirmed: true });
      setItems(prev => prev.map(i => i.id === item.id ? { ...i, confirmed: true, rejected: false } : i));
    } catch {}
  };

  const handleDecline = (item) => {
    setItems(prev => prev.map(i => i.id === item.id ? { ...i, rejected: true, confirmed: false } : i));
  };

  const handleRestore = (item) => {
    setItems(prev => prev.map(i => i.id === item.id ? { ...i, rejected: false, confirmed: false } : i));
  };

  const filtered = items.filter(i => {
    if (filterPriority !== 'all' && i.priority !== filterPriority) return false;
    if (filterStatus === 'confirmed' && !i.confirmed) return false;
    if (filterStatus === 'pending' && (i.confirmed || i.rejected)) return false;
    if (filterStatus === 'declined' && !i.rejected) return false;
    return true;
  });

  const stats = {
    total: items.length,
    confirmed: items.filter(i => i.confirmed).length,
    pending: items.filter(i => !i.confirmed && !i.rejected).length,
    high: items.filter(i => i.priority === 'high').length,
  };

  return (
    <><Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-txt mb-2">Action Items</h1>
          <p className="text-sm text-txtsec">Track and manage action items across all meetings.</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total', value: stats.total, cls: 'bg-blusoft text-blu' },
            { label: 'Confirmed', value: stats.confirmed, cls: 'bg-grnsoft text-grn' },
            { label: 'Pending', value: stats.pending, cls: 'bg-ambsoft text-amb' },
            { label: 'High Priority', value: stats.high, cls: 'bg-redsoft text-red' },
          ].map(({ label, value, cls }) => (
            <div key={label} className="bg-bgcard rounded-xl border border-bdr shadow-sm px-4 py-3">
              <span className="text-xs text-txttri">{label}</span>
              <span className={`text-2xl font-bold block mt-0.5 ${cls.split(' ')[1]}`}>{value}</span>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <select value={selectedMeeting} onChange={e => setSelectedMeeting(e.target.value)}
            className="px-3 py-2 bg-bgcard border border-bdr rounded-lg text-sm text-txt flex-1">
            <option value="all">All meetings</option>
            {meetings.map(m => <option key={m.id} value={m.id}>{m.title}{m.date ? ` — ${m.date}` : ''}</option>)}
          </select>
          <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)}
            className="px-3 py-2 bg-bgcard border border-bdr rounded-lg text-sm text-txt">
            <option value="all">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-bgcard border border-bdr rounded-lg text-sm text-txt">
            <option value="all">All statuses</option>
            <option value="confirmed">Confirmed</option>
            <option value="pending">Pending</option>
            <option value="declined">Declined</option>
          </select>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-redsoft border border-red/20 rounded-lg text-sm text-red flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 text-acc animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="bg-bgcard rounded-xl border border-bdr p-12 text-center">
            <ListChecks className="w-8 h-8 text-txttri mx-auto mb-3" />
            <p className="text-sm text-txtsec">No action items found{filterPriority !== 'all' || filterStatus !== 'all' ? ' matching your filters' : ''}.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map(item => (
              <ActionItemCard key={item.id} item={item} meetingTitle={selectedMeeting === 'all' ? item._meetingTitle : null}
                onConfirm={handleConfirm} onDecline={handleDecline} onRestore={handleRestore} />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
