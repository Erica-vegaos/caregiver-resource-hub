/* 聽見你搜尋 v1.1.1 — needs reflect actual coverage; disease scope is separate. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.YoubanSearch = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const CITIES = ['台北市','新北市','基隆市','桃園市','新竹市','新竹縣','苗栗縣','台中市','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','台南市','高雄市','屏東縣','宜蘭縣','花蓮縣','台東縣','澎湖縣','金門縣','連江縣'];
  const DAY = 86400000;
  const aliases = [
    [/雙相情緒障礙症?|雙相情感障礙症?|雙極性情感疾患|雙極性疾患|躁鬱症|躁鬱|雙極症|雙極|雙相/g, '雙相'],
    [/精神分裂症|思覺失調症|思覺失調/g, '思覺失調'],
    [/重度憂鬱症|重鬱症|重鬱/g, '重鬱'],
    [/照護者|照顧者/g, '照顧者']
  ];
  function normalize(value) {
    let text = String(value == null ? '' : value).normalize('NFKC').toLowerCase().replace(/臺/g, '台');
    aliases.forEach(([pattern, canonical]) => { text = text.replace(pattern, canonical); });
    return text.replace(/[\s　]+/g, ' ').trim();
  }
  function terms(query) { return [...new Set(normalize(query).split(/[\s,，、]+/).filter(Boolean))]; }
  function fields(event) {
    return {
      title: normalize(event.title),
      core: normalize([event.organizer,event.category,event.city,event.mode,...(event.tags || [])].join(' ')),
      body: normalize([event.summary,event.venue,event.eligibility,event.audience,...(event.notes || [])].join(' '))
    };
  }
  function matchText(text, query) { const hay = normalize(text); return terms(query).every(term => hay.includes(term)); }
  function relevance(event, query) {
    const parts = fields(event), list = terms(query), full = normalize(query);
    if (!list.length) return 0;
    const hay = [parts.title,parts.core,parts.body].join(' ');
    if (!list.every(term => hay.includes(term))) return -1;
    let score = parts.title === full ? 120 : parts.title.includes(full) ? 70 : 0;
    for (const term of list) score += parts.title.includes(term) ? 20 : parts.core.includes(term) ? 8 : 2;
    return score;
  }
  function taipeiDate(value) {
    const ms = typeof value === 'number' ? value : Date.parse(value);
    if (!Number.isFinite(ms)) return '';
    return new Date(ms + 8 * 3600000).toISOString().slice(0, 10);
  }
  function endTime(event) {
    const end = Date.parse(event.end);
    // A source with only a calendar date must not appear to end at midnight.
    return event.date_precision === 'date' ? Date.parse(taipeiDate(event.end || event.start) + 'T23:59:59+08:00') : end;
  }
  function derived(event, now = Date.now()) {
    const ended = endTime(event) < now || event.event_status === 'ended';
    const checked = Date.parse(event.checked_at);
    const stale = !Number.isFinite(checked) || now - checked > 72 * 3600000 || (event.freshness && event.freshness !== 'fresh');
    let status = event.registration_status || 'unknown';
    if (event.registration_deadline && Date.parse(event.registration_deadline) < now) status = 'closed';
    return { ended, stale: Boolean(stale), status };
  }
  function categoryMatch(actual, wanted) {
    if (!wanted || wanted === 'all') return true;
    const value = normalize(actual);
    if (wanted === '支持團體') return /支持團體|互助|家屬團體/.test(value);
    if (wanted === '講座與交流') return /講座|交流|座談/.test(value);
    if (wanted === '課程與工作坊') return /課程|工作坊|教育|培訓/.test(value);
    if (wanted === '紓壓活動') return /紓壓|喘息|休閒|戶外/.test(value);
    return value === normalize(wanted);
  }
  const TOPICS = {schizophrenia:'思覺失調', depression:'憂鬱症', bipolar:'躁鬱・雙相', general:'家屬通用支持', all:'所有主題'};
  function topicInfo(event) {
    // Organizer names and incidental notes are not evidence of an event's topic.
    const raw = normalize([event.title,event.summary,event.eligibility,...(event.tags || [])].join('。'));
    const clauses = raw.split(/[。；;，,\n]/);
    const negative = /不含|不包括|不接受|不開放|不適用|不收|排除/;
    const text = clauses.filter(clause=>!negative.test(clause)).join(' ');
    const patterns = {schizophrenia:/思覺失調/, depression:/憂鬱|重鬱/, bipolar:/雙相/};
    const excluded = Object.entries(patterns).filter(([,pattern])=>clauses.some(clause=>negative.test(clause)&&pattern.test(clause))).map(([key])=>key);
    const specific = Object.entries(patterns).filter(([,pattern])=>pattern.test(text)).map(([key])=>key);
    if (specific.length) return {topics:specific, general:false, excluded};
    const support = /家屬|照顧者|家人|家庭/.test(normalize(event.eligibility)) &&
      /支持|團體|聚會|交流|照顧|紓壓|休閒|共融/.test(normalize([event.title,event.category,event.summary].join(' ')));
    return {topics:[], general:event.caregiver_eligible === true && support && excluded.length===0, excluded};
  }
  function topicMatch(event, wanted, includeGeneral = false) {
    if (!wanted || wanted === 'all') return true;
    if (!Object.hasOwn(TOPICS,wanted)) return false;
    const info = topicInfo(event);
    if (info.excluded.includes(wanted)) return false;
    return wanted === 'general' ? info.general : info.topics.includes(wanted) || (includeGeneral && info.general);
  }
  const NEEDS = {exchange:'家屬交流與支持', learn:'照顧經驗與資源講座', relax:'運動與紓壓', community:'共融與休閒', all:'先看看全部'};
  function needMatch(event, wanted) {
    if (!wanted || wanted === 'all') return true;
    const text=normalize([event.title,...(event.tags||[])].join(' '));
    const community=/共融|嘉年華|園遊會/.test(text);
    if (wanted==='community') return community;
    if (wanted==='relax') return !community && categoryMatch(event.category,'紓壓活動');
    if (wanted==='exchange') return categoryMatch(event.category,'支持團體');
    if (wanted==='learn') return categoryMatch(event.category,'講座與交流') || categoryMatch(event.category,'課程與工作坊');
    return false;
  }
  function search(events, filters = {}, now = Date.now(), savedIds = []) {
    if (filters.from && filters.to && filters.from > filters.to) return [];
    const saved = savedIds instanceof Set ? savedIds : new Set(savedIds);
    const city = normalize(filters.city || 'all');
    const results = events.filter(event => {
      if (event.caregiver_eligible !== true || !Number.isFinite(Date.parse(event.start)) || !Number.isFinite(Date.parse(event.end))) return false;
      if (event.publication_status === 'rejected' || event.publication_status === 'quarantined') return false;
      if (filters.tab === 'saved' && !saved.has(event.id)) return false;
      if (city !== 'all' && normalize(event.city) !== city) return false;
      if (filters.mode && filters.mode !== 'all' && event.mode !== filters.mode && !(filters.mode === '線上' && event.mode === '混合')) return false;
      if (!categoryMatch(event.category, filters.category)) return false;
      if (!needMatch(event, filters.need)) return false;
      if (!topicMatch(event, filters.topic, filters.includeGeneral === true)) return false;
      const d = derived(event, now), start = Date.parse(event.start), end = endTime(event);
      const cancelled = event.event_status === 'cancelled';
      const period = filters.period || 'upcoming';
      if (period === 'upcoming' && (d.ended || cancelled)) return false;
      if (period === 'past' && !d.ended) return false;
      if (period === 'month' && (end < now || start > now + 30 * DAY || cancelled)) return false;
      if (filters.from && taipeiDate(end) < filters.from) return false;
      if (filters.to && taipeiDate(start) > filters.to) return false;
      if (filters.registration && filters.registration !== 'all') {
        if (d.status !== filters.registration) return false;
        if (filters.registration === 'open' && (d.stale || d.ended || cancelled)) return false;
      }
      return relevance(event, filters.query || '') >= 0;
    });
    const sort = filters.sort || 'relevance';
    return results.sort((a, b) => {
      if (filters.topic && !['all','general'].includes(filters.topic)) {
        const group = Number(topicInfo(a).general) - Number(topicInfo(b).general);
        if (group) return group;
      }
      if (sort === 'checked') return Date.parse(b.checked_at) - Date.parse(a.checked_at) || Date.parse(a.start) - Date.parse(b.start);
      if (sort === 'relevance' && terms(filters.query).length) {
        const delta = relevance(b, filters.query) - relevance(a, filters.query);
        if (delta) return delta;
      }
      return Date.parse(a.start) - Date.parse(b.start) || String(a.id).localeCompare(String(b.id));
    });
  }
  return { version:'1.1.1', CITIES, TOPICS, NEEDS, needMatch, topicInfo, topicMatch, normalize, terms, matchText, relevance, derived, taipeiDate, search };
});
