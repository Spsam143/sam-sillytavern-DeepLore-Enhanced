import time
from diagnostics.ring_buffer import RingBuffer

generation_buffer = RingBuffer(50)
started = False

_fr_title_map = {}
_fr_title_n = 0

def pseudo_title(title):
    global _fr_title_n
    if not title:
        return '?'
    p = _fr_title_map.get(title)
    if not p:
        _fr_title_n += 1
        p = f"<title-{_fr_title_n}>"
        _fr_title_map[title] = p
    return p

def _arr_len(trace, k):
    val = trace.get(k)
    return len(val) if isinstance(val, list) else 0

def summarize_trace(trace):
    if not trace or not isinstance(trace, dict):
        return None

    injected_titles = []
    if isinstance(trace.get('injected'), list):
        for e in trace['injected'][:30]:
            title = e.get('title') or e.get('filename') or '?'
            injected_titles.append(pseudo_title(title))

    budget = trace.get('budget')
    ai_pre_filter = trace.get('aiPreFilter')

    return {
        'keywordMatched': _arr_len(trace, 'keywordMatched'),
        'aiSelected': _arr_len(trace, 'aiSelected'),
        'gatedOut': _arr_len(trace, 'gatedOut'),
        'contextualGatingRemoved': _arr_len(trace, 'contextualGatingRemoved'),
        'cooldownRemoved': _arr_len(trace, 'cooldownRemoved'),
        'warmupFailed': _arr_len(trace, 'warmupFailed'),
        'refineKeyBlocked': _arr_len(trace, 'refineKeyBlocked'),
        'stripDedupRemoved': _arr_len(trace, 'stripDedupRemoved'),
        'budgetCut': _arr_len(trace, 'budgetCut'),
        'injected': _arr_len(trace, 'injected'),
        'injectedTitles': injected_titles,
        'bootstrapActive': bool(trace.get('bootstrapActive')),
        'aiFallback': bool(trace.get('aiFallback')),
        'aiError': trace.get('aiError'),
        'budget': {
            'used': budget.get('used') if budget else None,
            'limit': budget.get('limit') if budget else None,
            'ratio': budget.get('ratio') if budget else None,
        } if budget else None,
        'aiPreFilter': {
            'inputCount': ai_pre_filter.get('inputCount') if ai_pre_filter else None,
            'outputCount': ai_pre_filter.get('outputCount') if ai_pre_filter else None,
        } if ai_pre_filter else None,
        'genId': trace.get('genId'),
        'totalMs': trace.get('totalMs'),
        'keywordMatchMs': trace.get('keywordMatchMs'),
        'aiSearchMs': trace.get('aiSearchMs'),
        'ensureIndexFreshMs': trace.get('ensureIndexFreshMs'),
        'pinBlockMs': trace.get('pinBlockMs'),
        'contextualGatingMs': trace.get('contextualGatingMs'),
        'reinjectionCooldownMs': trace.get('reinjectionCooldownMs'),
        'requiresExcludesMs': trace.get('requiresExcludesMs'),
        'stripDedupMs': trace.get('stripDedupMs'),
        'formatGroupMs': trace.get('formatGroupMs'),
        'trackGenerationMs': trace.get('trackGenerationMs'),
        'recordAnalyticsMs': trace.get('recordAnalyticsMs'),
        'perChatCountsMs': trace.get('perChatCountsMs'),
    }

def record_abort(reason=None):
    try:
        generation_buffer.push({
            't': int(time.time() * 1000),
            'aborted': True,
            'reason': reason or 'unknown'
        })
    except Exception:
        pass

def start_flight_recorder(state_mod):
    global started
    if started:
        return
    started = True

    try:
        if not hasattr(state_mod, 'on_pipeline_complete'):
            print("[DLE] Flight recorder: on_pipeline_complete not found — generation recording disabled")
            started = False
            return

        generation_buffer.push({'t': int(time.time() * 1000), 'kind': 'recorder_started'})

        def callback():
            try:
                trace = getattr(state_mod, 'last_pipeline_trace', None)
                generation_buffer.push({
                    't': int(time.time() * 1000),
                    'genId': trace.get('genId') if trace else None,
                    'generationCount': getattr(state_mod, 'generation_count', None),
                    'chatEpoch': getattr(state_mod, 'chat_epoch', None),
                    'aiCircuitOpen': bool(getattr(state_mod, 'ai_circuit_open', False)),
                    'aiCircuitFailures': getattr(state_mod, 'ai_circuit_failures', 0),
                    'summary': summarize_trace(trace)
                })
            except Exception:
                try:
                    generation_buffer.push({'t': int(time.time() * 1000), 'error': 'trace summary failed'})
                except Exception:
                    pass

        state_mod.on_pipeline_complete(callback)
    except Exception as err:
        print(f"[DLE] Flight recorder start failed, will retry: {err}")
        started = False
