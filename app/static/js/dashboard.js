// Global State
let currentCategory = '';
let currentSearch = '';
let searchTimeout = null;
let timelineChart = null;
let currentLlmModel = 'qwen2.5:7b';

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  loadModels();
  loadDashboardData();
  loadMarketIntelligence();
  checkCrawlerStatus();
  
  // 15초마다 크롤러 상태 확인
  setInterval(checkCrawlerStatus, 15000);
});

async function loadModels() {
  try {
    const res = await fetch('/api/llm/models');
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById('llm-model-select');
    if (!select || !data.models) return;
    
    // 모델 옵션 갱신
    const models = data.models.filter(m => m.includes('qwen') || m.includes('gemma') || m.includes('exaone') || m.includes('mistral'));
    if (models.length > 0) {
      select.innerHTML = models.map(m => `
        <option value="${m}" ${m === currentLlmModel ? 'selected' : ''}>${m}</option>
      `).join('');
    }
  } catch (err) {
    console.error('Failed to load LLM models:', err);
  }
}

function changeLlmModel() {
  const select = document.getElementById('llm-model-select');
  currentLlmModel = select.value;
  document.getElementById('ai-badge-model').innerText = currentLlmModel;
  loadMarketIntelligence(false);
}

async function loadDashboardData() {
  await Promise.all([
    fetchSummary(),
    fetchSurgeKeywords(),
    fetchTopKeywordsAndWordCloud(),
    fetchTimeline(),
    fetchSectors(),
    fetchReports()
  ]);
}

// 0. AI Market Intelligence Brief
async function loadMarketIntelligence(forceRefresh = false) {
  const container = document.getElementById('ai-intel-content');
  if (forceRefresh) {
    container.innerHTML = `
      <div style="text-align: center; color: #cbd5e1; padding: 2rem;">
        <div class="spinner spinner-purple" style="margin-bottom: 0.5rem;"></div>
        <div>새로운 관점으로 마켓 인텔리전스를 재합성하고 있습니다...</div>
      </div>
    `;
  }
  
  try {
    const res = await fetch(`/api/market/ai-brief?model=${encodeURIComponent(currentLlmModel)}&refresh=${forceRefresh}`);
    if (!res.ok) throw new Error('API Error');
    const data = await res.json();
    
    const driversHtml = (data.key_drivers || []).map(d => `
      <div class="ai-driver-card">
        <div class="ai-driver-title">
          <span>⚡</span> ${d.driver}
        </div>
        <div class="ai-driver-detail">${d.detail}</div>
      </div>
    `).join('');
    
    const sectorsHtml = (data.hot_sectors || []).map(s => `
      <span class="ai-sector-pill"># ${s}</span>
    `).join('');
    
    const sourcesHtml = (data.source_reports || []).map(r => `
      <div class="ai-source-item">
        <div class="ai-source-info">
          <span class="cat-badge cat-company" style="font-size:0.7rem; padding:0.1rem 0.4rem;">${r.broker || '증권'}</span>
          <span class="ai-source-title" onclick="openReportAiModal(${r.id}, '${escapeHtml(r.title)}')">
            ${r.company_or_sector ? `[${r.company_or_sector}] ` : ''}${r.title}
          </span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <span class="ai-source-meta">${r.report_date}</span>
          ${r.pdf_url ? `<a href="${r.pdf_url}" target="_blank" class="pdf-btn" style="padding:0.15rem 0.4rem; font-size:0.7rem;">PDF ↗</a>` : ''}
        </div>
      </div>
    `).join('');
    
    container.innerHTML = `
      <div class="ai-headline">"${data.headline || '시장 인텔리전스'}"</div>
      <div class="ai-summary-body">${data.market_summary || ''}</div>
      
      <div class="ai-drivers-grid">
        ${driversHtml}
      </div>
      
      <div class="ai-intel-footer">
        <div class="ai-sectors-taglist">
          <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">집중 관심 섹터:</span>
          ${sectorsHtml}
        </div>
        ${data.actionable_insight ? `<div class="ai-action-tip">💡 ${data.actionable_insight}</div>` : ''}
      </div>

      ${sourcesHtml ? `
        <div class="ai-sources-container">
          <div class="ai-sources-header" onclick="toggleSourcesList()">
            <div class="ai-sources-title">
              <span>📚</span> 분석 근거 원본 리포트 (${(data.source_reports || []).length}건)
            </div>
            <span id="sources-toggle-icon" style="font-size: 0.8rem; color: var(--text-muted);">▼ 접기/펼치기</span>
          </div>
          <div class="ai-sources-list" id="ai-sources-list-box">
            ${sourcesHtml}
          </div>
        </div>
      ` : ''}
    `;
  } catch (err) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
        마켓 인텔리전스 생성 대기 중입니다. 우측 상단의 [다시 생성]을 클릭해 보세요.
      </div>
    `;
  }
}

function toggleSourcesList() {
  const box = document.getElementById('ai-sources-list-box');
  if (box) {
    box.style.display = box.style.display === 'none' ? 'grid' : 'none';
  }
}

// 1. Summary KPIs
async function fetchSummary() {
  try {
    const res = await fetch('/api/summary');
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('stat-total-reports').innerText = `${data.total_reports}건`;
    document.getElementById('stat-processed-reports').innerText = `${data.processed_reports}건`;
    document.getElementById('stat-total-sectors').innerText = `${data.total_sectors}개`;
    
    if (data.hot_themes && data.hot_themes.length > 0) {
      document.getElementById('stat-hot-theme').innerText = data.hot_themes.join(', ');
    } else {
      document.getElementById('stat-hot-theme').innerText = '수집 대기 중';
    }
  } catch (err) {
    console.error('Failed to fetch summary:', err);
  }
}

// 2. Surge Keywords
async function fetchSurgeKeywords() {
  try {
    const res = await fetch('/api/surge?top_n=10');
    const container = document.getElementById('surge-container');
    if (!res.ok) return;
    
    const items = await res.json();
    if (!items || items.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 2.5rem;">
          수집된 리포트 텍스트가 아직 부족합니다.<br>
          상단의 <b>[최신 리포트 수집 & 분석]</b>을 실행해 보세요!
        </div>`;
      return;
    }
    
    container.innerHTML = items.map((item, index) => {
      const isTop = index < 3;
      return `
        <div class="surge-item" onclick="openThemeAiModal('${item.keyword}')">
          <div class="surge-keyword-info">
            <span class="surge-rank ${isTop ? 'rank-top' : ''}">${index + 1}</span>
            <span class="surge-keyword-name">${item.keyword}</span>
          </div>
          <div class="surge-metrics">
            <span class="surge-count">최근 ${item.recent_count}회</span>
            <span class="surge-ratio">+${item.growth_ratio}x</span>
            <button class="btn-ai-mini">✨ AI 브리프</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to fetch surge:', err);
  }
}

// 3. WordCloud & Top Keywords
async function fetchTopKeywordsAndWordCloud() {
  try {
    const res = await fetch('/api/keywords/top?top_n=50');
    if (!res.ok) return;
    
    const keywords = await res.json();
    const canvas = document.getElementById('wordcloud-canvas');
    if (!canvas || !keywords || keywords.length === 0) return;
    
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = 360;
    
    const list = keywords.map(k => [k.text, k.value]);
    const maxVal = Math.max(...keywords.map(k => k.value), 1);
    
    WordCloud(canvas, {
      list: list,
      gridSize: 8,
      weightFactor: function (size) {
        return Math.max(14, (size / maxVal) * 48);
      },
      fontFamily: 'Outfit, Pretendard, sans-serif',
      color: function () {
        const colors = ['#38bdf8', '#818cf8', '#34d399', '#f472b6', '#fbbf24', '#a78bfa', '#2dd4bf'];
        return colors[Math.floor(Math.random() * colors.length)];
      },
      backgroundColor: 'transparent',
      rotateRatio: 0.25,
      rotationSteps: 2,
      minRotation: -Math.PI / 6,
      maxRotation: Math.PI / 6,
      shuffle: true,
      click: function(item) {
        openThemeAiModal(item[0]);
      }
    });
  } catch (err) {
    console.error('Failed to render wordcloud:', err);
  }
}

// 4. Timeline Line Chart
async function fetchTimeline() {
  try {
    const res = await fetch('/api/timeline?top_n=5');
    if (!res.ok) return;
    
    const data = await res.json();
    const ctx = document.getElementById('timeline-chart');
    if (!ctx || !data.dates || data.dates.length === 0) return;
    
    const colors = [
      { border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.1)' },
      { border: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.1)' },
      { border: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' },
      { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' },
      { border: '#ec4899', bg: 'rgba(236, 72, 153, 0.1)' },
    ];
    
    const datasets = data.series.map((s, idx) => {
      const color = colors[idx % colors.length];
      return {
        label: s.name,
        data: s.data,
        borderColor: color.border,
        backgroundColor: color.bg,
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointBackgroundColor: color.border,
        pointRadius: 4,
        pointHoverRadius: 6
      };
    });
    
    if (timelineChart) timelineChart.destroy();
    
    timelineChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.dates,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              color: '#9ca3af',
              font: { family: 'Outfit, sans-serif', size: 12, weight: 'bold' },
              usePointStyle: true,
              boxWidth: 8
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#6b7280', font: { size: 11 } }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#6b7280', font: { size: 11 }, precision: 0 }
          }
        }
      }
    });
  } catch (err) {
    console.error('Failed to fetch timeline:', err);
  }
}

// 5. Sectors & Keywords
async function fetchSectors() {
  try {
    const res = await fetch('/api/sectors?top_n=6');
    const container = document.getElementById('sector-container');
    if (!res.ok) return;
    
    const sectors = await res.json();
    if (!sectors || sectors.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 2rem;">섹터 데이터가 없습니다.</div>';
      return;
    }
    
    container.innerHTML = sectors.map(sec => `
      <div class="sector-item">
        <div class="sector-header">
          <span class="sector-name">${sec.sector}</span>
          <span class="sector-count">${sec.report_count}개 리포트</span>
        </div>
        <div class="sector-tags">
          ${sec.top_keywords.map(kw => `<span class="sector-keyword-tag" onclick="openThemeAiModal('${kw.split('(')[0]}')" style="cursor:pointer;">${kw}</span>`).join('')}
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to fetch sectors:', err);
  }
}

// 6. Reports Explorer
async function fetchReports() {
  try {
    let url = `/api/reports?limit=50`;
    if (currentCategory) url += `&category=${currentCategory}`;
    if (currentSearch) url += `&keyword=${encodeURIComponent(currentSearch)}`;
    
    const res = await fetch(url);
    const tbody = document.getElementById('reports-table-body');
    if (!res.ok) return;
    
    const reports = await res.json();
    if (!reports || reports.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">
            검색 결과에 해당하는 리포트가 없습니다.
          </td>
        </tr>
      `;
      return;
    }
    
    const categoryMap = {
      'company': { name: '기업', cls: 'cat-company' },
      'industry': { name: '산업', cls: 'cat-industry' },
      'market': { name: '시황', cls: 'cat-market' },
    };
    
    tbody.innerHTML = reports.map(r => {
      const cat = categoryMap[r.category] || { name: r.category, cls: 'cat-company' };
      const summary = r.summary_text ? `<div class="report-summary-text">${r.summary_text}</div>` : '';
      
      return `
        <tr>
          <td><span class="cat-badge ${cat.cls}">${cat.name}</span></td>
          <td><strong style="color: #e2e8f0;">${r.company_or_sector || '-'}</strong></td>
          <td>
            <a href="javascript:void(0)" onclick="openReportAiModal(${r.id}, '${escapeHtml(r.title)}')" class="report-title-link">
              ${r.title}
            </a>
            ${summary}
          </td>
          <td>${r.broker || '-'}</td>
          <td style="font-size: 0.85rem; color: #94a3b8;">${r.report_date}</td>
          <td>
            <div class="table-actions">
              <button class="btn-table-ai" onclick="openReportAiModal(${r.id}, '${escapeHtml(r.title)}')">
                <span>🤖</span> AI요약
              </button>
              <a href="${r.pdf_url}" target="_blank" class="pdf-btn">
                <span>PDF</span> ↗
              </a>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to fetch reports:', err);
  }
}

// Modal Functions
function openModal(titleHtml) {
  const modal = document.getElementById('ai-modal');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');
  
  title.innerHTML = titleHtml;
  body.innerHTML = `
    <div style="text-align: center; padding: 3rem; color: #94a3b8;">
      <div class="spinner spinner-purple" style="margin-bottom: 0.75rem;"></div>
      <div>로컬 AI (${currentLlmModel})가 심층 분석을 생성하고 있습니다...</div>
    </div>
  `;
  modal.classList.add('active');
}

function closeModal() {
  document.getElementById('ai-modal').classList.remove('active');
}

function handleModalBackdropClick(e) {
  if (e.target.id === 'ai-modal') {
    closeModal();
  }
}

// Open Single Report AI Modal
async function openReportAiModal(reportId, reportTitle) {
  openModal(`<span>📑</span> 리포트 AI 3줄 요약 <span class="badge-tag" style="margin-left:8px;">${currentLlmModel}</span>`);
  
  try {
    const res = await fetch(`/api/reports/${reportId}/ai-summary?model=${encodeURIComponent(currentLlmModel)}`);
    const body = document.getElementById('modal-body');
    if (!res.ok) throw new Error('Failed to summarize');
    
    const data = await res.json();
    
    let sentimentClass = 'sentiment-neutral';
    if ((data.sentiment || '').includes('긍정') || (data.sentiment || '').includes('Bullish')) sentimentClass = 'sentiment-bullish';
    if ((data.sentiment || '').includes('신중') || (data.sentiment || '').includes('Bearish')) sentimentClass = 'sentiment-bearish';
    
    const pointsHtml = (data.investment_points || []).map(p => `<li>${p}</li>`).join('');
    const risksHtml = (data.risk_factors || []).map(r => `<li>${r}</li>`).join('');
    
    body.innerHTML = `
      <div style="margin-bottom: 1.25rem;">
        <div style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 0.25rem;">대상 리포트</div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">${reportTitle}</div>
      </div>

      <div class="modal-section">
        <div class="modal-section-title">
          <span>🎯</span> 한 줄 핵심 결론
          <span class="sentiment-badge ${sentimentClass}" style="margin-left: auto;">${data.sentiment || '중립'}</span>
        </div>
        <div class="modal-one-liner">${data.one_line_summary || '-'}</div>
      </div>

      <div class="modal-section">
        <div class="modal-section-title"><span>📌</span> 핵심 투자 포인트 (Investment Points)</div>
        <ul class="modal-list">
          ${pointsHtml || '<li>내용 없음</li>'}
        </ul>
      </div>

      ${data.financial_outlook ? `
        <div class="modal-section">
          <div class="modal-section-title"><span>📊</span> 실적 전망 & 목표주가 산정 근거</div>
          <div style="font-size: 0.9rem; color: #cbd5e1; background: rgba(0,0,0,0.25); padding: 0.75rem 1rem; border-radius: 8px; line-height: 1.5;">
            ${data.financial_outlook}
          </div>
        </div>
      ` : ''}

      ${risksHtml ? `
        <div class="modal-section">
          <div class="modal-section-title" style="color: #f87171;"><span>⚠️</span> 주요 리스크 및 변수</div>
          <ul class="modal-list">
            ${risksHtml}
          </ul>
        </div>
      ` : ''}
    `;
  } catch (err) {
    document.getElementById('modal-body').innerHTML = `
      <div style="text-align: center; color: #f87171; padding: 2rem;">
        AI 요약 생성 중 오류가 발생했습니다.<br>
        Ollama 서비스 상태를 확인해 주세요.
      </div>
    `;
  }
}

// Open Theme AI Brief Modal
async function openThemeAiModal(themeName) {
  openModal(`<span>🚀</span> 테마 종합 AI 브리프 : <b style="color:#38bdf8;">${themeName}</b>`);
  
  try {
    const res = await fetch(`/api/themes/${encodeURIComponent(themeName)}/ai-brief?model=${encodeURIComponent(currentLlmModel)}`);
    const body = document.getElementById('modal-body');
    if (!res.ok) throw new Error('Failed to generate brief');
    
    const data = await res.json();
    
    const beneficiariesHtml = (data.top_beneficiaries || []).map(b => `
      <span class="ai-sector-pill" style="font-size:0.85rem; padding:0.3rem 0.7rem;">${b}</span>
    `).join('');
    
    const catalystsHtml = (data.catalysts || []).map(c => `<li>${c}</li>`).join('');
    const risksHtml = (data.risk_points || []).map(r => `<li>${r}</li>`).join('');
    
    body.innerHTML = `
      <div class="modal-section">
        <div class="modal-section-title"><span>🔥</span> 시장 주목 배경 & 모멘텀</div>
        <div class="modal-one-liner" style="border-left-color: #38bdf8; background: rgba(56, 189, 248, 0.08);">
          ${data.market_driver || '-'}
        </div>
      </div>

      <div class="modal-section">
        <div class="modal-section-title"><span>📑</span> 증권가 컨센서스 & 핵심 시각</div>
        <div style="font-size: 0.95rem; color: #e2e8f0; background: rgba(0,0,0,0.3); padding: 0.9rem 1.1rem; border-radius: 8px; line-height: 1.6;">
          ${data.consensus || '-'}
        </div>
      </div>

      ${beneficiariesHtml ? `
        <div class="modal-section">
          <div class="modal-section-title"><span>🏆</span> 주요 수혜 기업 & 관련 종목</div>
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem;">
            ${beneficiariesHtml}
          </div>
        </div>
      ` : ''}

      ${catalystsHtml ? `
        <div class="modal-section">
          <div class="modal-section-title"><span>🚀</span> 향후 상승 촉매 (Catalysts)</div>
          <ul class="modal-list">
            ${catalystsHtml}
          </ul>
        </div>
      ` : ''}

      ${risksHtml ? `
        <div class="modal-section">
          <div class="modal-section-title" style="color: #f87171;"><span>⚠️</span> 투자 유의점 & 리스크</div>
          <ul class="modal-list">
            ${risksHtml}
          </ul>
        </div>
      ` : ''}

      ${(data.source_reports && data.source_reports.length > 0) ? `
        <div class="modal-section" style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.08);">
          <div class="modal-section-title" style="color: #93c5fd;"><span>📚</span> 분석에 참고한 원본 리포트 (${data.source_reports.length}건)</div>
          <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem;">
            ${data.source_reports.map(r => `
              <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.02); padding:0.45rem 0.75rem; border-radius:6px; font-size:0.8rem; border:1px solid rgba(255,255,255,0.04);">
                <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; margin-right:0.5rem;">
                  <span class="cat-badge cat-company" style="font-size:0.68rem; padding:0.1rem 0.35rem; margin-right:0.35rem;">${r.broker || '증권'}</span>
                  <span style="color:#e2e8f0; cursor:pointer;" onclick="openReportAiModal(${r.id}, '${escapeHtml(r.title)}')">${r.title}</span>
                </div>
                <div style="display:flex; align-items:center; gap:0.4rem; white-space:nowrap;">
                  <span style="color:var(--text-muted); font-size:0.72rem;">${r.report_date}</span>
                  ${r.pdf_url ? `<a href="${r.pdf_url}" target="_blank" class="pdf-btn" style="padding:0.15rem 0.4rem; font-size:0.7rem;">PDF ↗</a>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
    `;
  } catch (err) {
    document.getElementById('modal-body').innerHTML = `
      <div style="text-align: center; color: #f87171; padding: 2rem;">
        테마 브리프 생성 중 오류가 발생했습니다.
      </div>
    `;
  }
}

// Helpers
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function filterReports(category) {
  currentCategory = category;
  const buttons = document.querySelectorAll('.filter-btn');
  buttons.forEach(btn => {
    if ((category === '' && btn.innerText === '전체') ||
        (category === 'company' && btn.innerText === '기업 리포트') ||
        (category === 'industry' && btn.innerText === '산업 분석') ||
        (category === 'market' && btn.innerText === '시황/전략')) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  fetchReports();
}

function debounceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    const input = document.getElementById('report-search');
    currentSearch = input.value.trim();
    fetchReports();
  }, 300);
}

// Crawler Trigger
async function triggerCrawl() {
  const btn = document.getElementById('btn-run-crawler');
  const icon = document.getElementById('crawler-btn-icon');
  const text = document.getElementById('crawler-btn-text');
  
  btn.disabled = true;
  icon.innerHTML = '<div class="spinner"></div>';
  text.innerText = '수집 & 분석 중...';
  
  try {
    const res = await fetch('/api/pipeline/run?pages=2&max_pdfs=35', { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    pollCrawlerStatus();
  } catch (err) {
    alert('작업 시작 요청 중 오류가 발생했습니다.');
    resetCrawlButton();
  }
}

async function checkCrawlerStatus() {
  try {
    const res = await fetch('/api/pipeline/status');
    if (!res.ok) return;
    const data = await res.json();
    if (data.is_running) setButtonCrawlingState();
    else resetCrawlButton();
  } catch (err) {}
}

function setButtonCrawlingState() {
  const btn = document.getElementById('btn-run-crawler');
  const icon = document.getElementById('crawler-btn-icon');
  const text = document.getElementById('crawler-btn-text');
  btn.disabled = true;
  icon.innerHTML = '<div class="spinner"></div>';
  text.innerText = '백그라운드 수집/분석 중...';
}

function resetCrawlButton() {
  const btn = document.getElementById('btn-run-crawler');
  const icon = document.getElementById('crawler-btn-icon');
  const text = document.getElementById('crawler-btn-text');
  btn.disabled = false;
  icon.innerHTML = '⚡';
  text.innerText = '최신 리포트 수집 & 분석';
}

function pollCrawlerStatus() {
  const interval = setInterval(async () => {
    try {
      const res = await fetch('/api/pipeline/status');
      const data = await res.json();
      if (!data.is_running) {
        clearInterval(interval);
        resetCrawlButton();
        loadDashboardData();
        loadMarketIntelligence(true);
      }
    } catch (err) {
      clearInterval(interval);
      resetCrawlButton();
    }
  }, 4000);
}
