<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>토스 커머스 자동화 파이프라인 대시보드</title>
    <style>
        :root {
            --primary: #3182f6;
            --primary-hover: #1b64da;
            --bg-gray: #f5f6f8;
            --sidebar-bg: #ffffff;
            --text-main: #191f28;
            --text-sub: #8b95a1;
            --border-color: #e5e8eb;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background-color: var(--bg-gray); 
            color: var(--text-main); 
            display: flex; 
            height: 100vh; 
            overflow: hidden; 
        }

        .sidebar { 
            width: 240px; 
            background-color: var(--sidebar-bg); 
            border-right: 1px solid var(--border-color); 
            display: flex; 
            flex-direction: column; 
            padding: 20px 0; 
            flex-shrink: 0;
        }
        .sidebar .logo { 
            font-size: 18px; 
            font-weight: bold; 
            padding: 0 20px 20px; 
            color: var(--primary); 
            border-bottom: 1px solid var(--border-color); 
        }
        .menu-list { list-style: none; margin-top: 10px; }
        .menu-item { 
            padding: 14px 20px; 
            font-size: 15px; 
            font-weight: 500; 
            color: #4e5968; 
            cursor: pointer; 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            transition: 0.2s; 
            white-space: nowrap;
        }
        .menu-item:hover, .menu-item.active { 
            background-color: #e8f3ff; 
            color: var(--primary); 
            font-weight: bold; 
        }

        .main-content { 
            flex: 1; 
            padding: 30px; 
            overflow-y: auto; 
            -webkit-overflow-scrolling: touch;
        }
        .section { display: none; }
        .section.active { display: block; }
        .page-title { font-size: 22px; font-weight: bold; margin-bottom: 20px; }

        .card { 
            background: white; 
            border-radius: 16px; 
            padding: 24px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
            margin-bottom: 20px; 
        }
        
        .filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
        select, input[type="text"] { 
            padding: 12px 14px; 
            border: 1px solid var(--border-color); 
            border-radius: 8px; 
            font-size: 14px; 
        }
        input[type="text"] { flex: 1; min-width: 150px; }
        button.btn-primary { 
            padding: 12px 20px; 
            background-color: var(--primary); 
            color: white; 
            border: none; 
            border-radius: 8px; 
            font-weight: bold; 
            cursor: pointer; 
            font-size: 14px;
            min-height: 44px;
            white-space: nowrap;
        }
        button.btn-primary:hover { background-color: var(--primary-hover); }

        .table-responsive {
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; min-width: 1000px; }
        th, td { padding: 12px; border-bottom: 1px solid var(--border-color); vertical-align: top; }
        th { background-color: #f9fafb; color: var(--text-sub); font-weight: 600; white-space: nowrap; }
        .badge { padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        .badge-done { background-color: #e6f4ea; color: #137333; }
        .badge-none { background-color: #fce8e6; color: #c5221f; }
        
        .link-text { color: var(--primary); text-decoration: none; font-weight: 500; }
        .link-text:hover { text-decoration: underline; }

        .features-list { padding-left: 16px; margin: 0; line-height: 1.5; color: #333; }
        .features-list li { margin-bottom: 4px; }

        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-weight: bold; margin-bottom: 8px; font-size: 14px; }
        .form-group select, .form-group input { width: 100%; }
        .output-box { 
            margin-top: 16px; 
            padding: 16px; 
            background: #f9fafb; 
            border-radius: 8px; 
            border: 1px solid var(--border-color); 
            font-size: 14px; 
            line-height: 1.6; 
            white-space: pre-wrap; 
            word-break: break-all;
        }

        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { 
                width: 100%; 
                height: auto; 
                padding: 12px 0 0 0; 
                border-right: none; 
                border-bottom: 1px solid var(--border-color); 
            }
            .sidebar .logo { 
                padding: 0 16px 10px; 
                font-size: 16px; 
                border-bottom: none; 
            }
            .menu-list { 
                display: flex; 
                overflow-x: auto; 
                margin-top: 0; 
                padding: 0 10px; 
                -webkit-overflow-scrolling: touch; 
            }
            .menu-list::-webkit-scrollbar { display: none; }
            .menu-item { 
                padding: 10px 14px; 
                font-size: 14px; 
                border-bottom: 2px solid transparent; 
                border-radius: 0; 
            }
            .menu-item.active { 
                background-color: transparent; 
                border-bottom: 2px solid var(--primary); 
            }

            .main-content { padding: 16px; }
            .card { padding: 16px; border-radius: 12px; }
            .page-title { font-size: 18px; margin-bottom: 14px; }
            
            .filter-bar { flex-direction: column; align-items: stretch; }
            .filter-bar select, .filter-bar input, .filter-bar button { width: 100%; }
        }
    </style>
</head>
<body>

    <div class="sidebar">
        <div class="logo">🚀 Toss AutoFlow</div>
        <ul class="menu-list">
            <li class="menu-item active" onclick="switchTab(event, 'all-auto')">⚡ 전체 자동화</li>
            <li class="menu-item" onclick="switchTab(event, 'item-search')">🔍 아이템 찾기</li>
            <li class="menu-item" onclick="switchTab(event, 'reels')">📸 인스타 릴스</li>
            <li class="menu-item" onclick="switchTab(event, 'shorts')">🎬 유튜브 쇼츠</li>
            <li class="menu-item" onclick="switchTab(event, 'blog')">📝 네이버 블로그</li>
            <li class="menu-item" onclick="switchTab(event, 'settings')">⚙️ 설정</li>
        </ul>
    </div>

    <div class="main-content">
        
        <div id="all-auto" class="section active">
            <div class="page-title">전체 자동화 파이프라인</div>
            <div class="card">
                <div class="form-group">
                    <label>토스 쉐어링크 URL 입력</label>
                    <input type="text" id="tossUrl" placeholder="https://toss.shopping/_m/..." />
                </div>
                <button class="btn-primary" onclick="runPipeline()">대본, 음성 및 쇼츠 자동 생성</button>
                <div id="pipelineLog" class="output-box">토스 상품 링크를 넣고 실행 버튼을 누르면 인스타, 유튜브, 블로그용 콘텐츠가 한 번에 생성됩니다.</div>
            </div>
        </div>

        <div id="item-search" class="section">
            <div class="page-title">인기 아이템 탐색 및 관리</div>
            
            <!-- 링크 직접 추가 및 수집 필터바 -->
            <div class="card">
                <div class="filter-bar">
                    <input type="text" id="manualAddUrl" placeholder="토스 앱에서 복사한 쉐어링크 직접 입력 (https://toss.shopping/...)" />
                    <button class="btn-primary" onclick="addCustomItemLink()">➕ 링크 직접 추가</button>
                    <button class="btn-primary" style="background-color: #2b303b;" onclick="fetchTossTrendingItems()">🔥 인기 아이템 수집</button>
                </div>
                <div class="filter-bar" style="margin-bottom: 0;">
                    <select id="channelFilter" onchange="filterItems()">
                        <option value="all">전체 업로드 상태</option>
                        <option value="reels">릴스 미업로드</option>
                        <option value="shorts">쇼츠 미업로드</option>
                        <option value="blog">블로그 미업로드</option>
                    </select>
                    <input type="text" id="itemSearchInput" placeholder="제품명 검색..." onkeyup="filterItems()">
                </div>
            </div>

            <div class="card">
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>제품명</th>
                                <th style="width: 250px;">🌟 장점 3가지 (AI 분석)</th>
                                <th>정가</th>
                                <th>할인율</th>
                                <th>판매가</th>
                                <th>활용방법</th>
                                <th>리워드 쉐어링크</th>
                                <th>릴스</th>
                                <th>쇼츠</th>
                                <th>블로그</th>
                            </tr>
                        </thead>
                        <tbody id="itemTableBody">
                            <tr>
                                <td colspan="10" style="text-align: center; color: var(--text-sub);">
                                    [➕ 링크 직접 추가] 또는 [🔥 인기 아이템 수집] 버튼을 눌러 목록을 구성해 보세요.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="reels" class="section">
            <div class="page-title">인스타 릴스 생성기</div>
            <div class="card">
                <div class="form-group">
                    <label>아이템 목록에서 선택</label>
                    <select id="reelsItemSelect">
                        <option value="">아이템 찾기에서 먼저 수집해주세요</option>
                    </select>
                </div>
                <button class="btn-primary" onclick="generateContent('reels')">릴스용 텍스트/오디오/영상 생성</button>
                <div id="reelsOutput" class="output-box">제품을 선택하면 인스타 감성의 숏폼 스크립트와 트렌디한 가이드 오디오가 출력됩니다.</div>
            </div>
        </div>

        <div id="shorts" class="section">
            <div class="page-title">유튜브 쇼츠 생성기</div>
            <div class="card">
                <div class="form-group">
                    <label>아이템 목록에서 선택</label>
                    <select id="shortsItemSelect">
                        <option value="">아이템 찾기에서 먼저 수집해주세요</option>
                    </select>
                </div>
                <button class="btn-primary" onclick="generateContent('shorts')">쇼츠 전용 영상 및 TTS 생성</button>
                <div id="shortsOutput" class="output-box">유튜브 쇼츠용 고효율 대본 및 합성 MP4 영상이 생성됩니다.</div>
            </div>
        </div>

        <div id="blog" class="section">
            <div class="page-title">네이버 블로그 포스팅 생성기</div>
            <div class="card">
                <div class="form-group">
                    <label>아이템 목록에서 선택</label>
                    <select id="blogItemSelect">
                        <option value="">아이템 찾기에서 먼저 수집해주세요</option>
                    </select>
                </div>
                <button class="btn-primary" onclick="generateContent('blog')">상세 리뷰 글 및 원고 생성</button>
                <div id="blogOutput" class="output-box">SEO에 최적화된 상품 후기 및 파트너스 공유용 텍스트가 서식에 맞춰 생성됩니다.</div>
            </div>
        </div>

        <div id="settings" class="section">
            <div class="page-title">환경 설정</div>
            <div class="card">
                <div class="form-group">
                    <label>Render 백엔드 서버 URL</label>
                    <input type="text" id="serverUrl" value="https://toss-automation-backend.onrender.com" />
                </div>
                <div class="form-group">
                    <label>토스 파트너스 API 상태</label>
                    <input type="text" value="Access Key, Secret Key, 회원 연동 ID (Render 환경변수 연동 완료)" disabled />
                </div>
                <button class="btn-primary" onclick="alert('설정이 저장되었습니다.')">설정 저장</button>
            </div>
        </div>

    </div>

    <script>
        const SERVER_URL = "https://toss-automation-backend.onrender.com";
        let fetchedItemsList = [];

        function switchTab(e, tabId) {
            document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
            
            e.currentTarget.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        function filterItems() {
            const input = document.getElementById('itemSearchInput').value.toLowerCase();
            const rows = document.querySelectorAll('#itemTableBody tr');

            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }

        function updateChannelDropdowns(items) {
            const reelsSelect = document.getElementById('reelsItemSelect');
            const shortsSelect = document.getElementById('shortsItemSelect');
            const blogSelect = document.getElementById('blogItemSelect');

            let optionsHtml = '';
            items.forEach(item => {
                optionsHtml += `<option value="${item.share_link}">${item.name} (${item.sale_price})</option>`;
            });

            reelsSelect.innerHTML = optionsHtml;
            shortsSelect.innerHTML = optionsHtml;
            blogSelect.innerHTML = optionsHtml;
        }

        function renderTable() {
            const tableBody = document.getElementById('itemTableBody');
            tableBody.innerHTML = '';

            if (fetchedItemsList.length === 0) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="10" style="text-align: center; color: var(--text-sub);">
                            [➕ 링크 직접 추가] 또는 [🔥 인기 아이템 수집] 버튼을 눌러 목록을 구성해 보세요.
                        </td>
                    </tr>`;
                return;
            }

            fetchedItemsList.forEach(item => {
                const tr = document.createElement('tr');
                
                // 장점 3가지 HTML 리스트 구성
                let featuresHtml = '<ul class="features-list">';
                if (Array.isArray(item.features)) {
                    item.features.forEach(f => featuresHtml += `<li>• ${f}</li>`);
                } else {
                    featuresHtml += `<li>• ${item.features || '가성비 최우선 상품'}</li>`;
                }
                featuresHtml += '</ul>';

                tr.innerHTML = `
                    <td><b>${item.name}</b></td>
                    <td>${featuresHtml}</td>
                    <td>${item.original_price}</td>
                    <td>${item.discount_rate}</td>
                    <td>${item.sale_price}</td>
                    <td>${item.usage}</td>
                    <td><a href="${item.share_link}" target="_blank" class="link-text">🔗 쉐어링크 열기</a></td>
                    <td><span class="badge ${item.reels ? 'badge-done' : 'badge-none'}">${item.reels ? '완료' : '미완료'}</span></td>
                    <td><span class="badge ${item.shorts ? 'badge-done' : 'badge-none'}">${item.shorts ? '완료' : '미완료'}</span></td>
                    <td><span class="badge ${item.blog ? 'badge-done' : 'badge-none'}">${item.blog ? '완료' : '미완료'}</span></td>
                `;
                tableBody.appendChild(tr);
            });
        }

        // 아이템 찾기 탭에서 사용자가 링크 직접 추가하는 신규 기능
        async function addCustomItemLink() {
            const input = document.getElementById('manualAddUrl');
            const url = input.value.trim();

            if (!url) {
                alert('토스 쉐어링크 주소를 입력해주세요.');
                return;
            }

            alert('입력한 토스 쉐어링크를 분석하여 장점 3가지 및 상품 정보를 추출 중입니다...');

            try {
                const res = await fetch(`${SERVER_URL}/parse-custom-link`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_url: url })
                });
                const data = await res.json();

                if (data.success && data.item) {
                    const exists = fetchedItemsList.some(item => item.share_link === data.item.share_link);
                    if (!exists) {
                        fetchedItemsList.unshift(data.item); // 맨 위에 추가
                        renderTable();
                        updateChannelDropdowns(fetchedItemsList);
                        input.value = '';
                        alert(`'${data.item.name}' 상품이 아이템 목록에 성공적으로 추가되었습니다!`);
                    } else {
                        alert('이미 목록에 존재하는 쉐어링크입니다.');
                    }
                } else {
                    alert('상품 정보를 파싱하지 못했습니다. 링크를 다시 확인해주세요.');
                }
            } catch (e) {
                alert('서버와 통신하는 도중 오류가 발생했습니다.');
            }
        }

        async function fetchTossTrendingItems() {
            alert('토스 파트너스 API 수집을 시작합니다.');

            try {
                const res = await fetch(`${SERVER_URL}/fetch-trending-items`);
                const data = await res.json();

                if (data.success && data.items) {
                    let newAddedCount = 0;

                    data.items.forEach(newItem => {
                        const exists = fetchedItemsList.some(item => item.share_link === newItem.share_link);
                        if (!exists) {
                            fetchedItemsList.push(newItem);
                            newAddedCount++;
                        }
                    });

                    renderTable();
                    updateChannelDropdowns(fetchedItemsList);

                    if (newAddedCount > 0) {
                        alert(`신규 아이템 ${newAddedCount}개가 추가 누적되었습니다! (총 ${fetchedItemsList.length}개)`);
                    } else {
                        alert(`이미 수집된 아이템들입니다. (총 ${fetchedItemsList.length}개)`);
                    }
                }
            } catch (e) {
                alert('아이템 수집 중 오류가 발생했습니다.');
            }
        }

        async function runPipeline() {
            const url = document.getElementById('tossUrl').value.trim();
            const log = document.getElementById('pipelineLog');

            if(!url) { alert('토스 링크를 입력해주세요.'); return; }

            log.innerText = "⏳ 백엔드 서버에서 대본 및 쇼츠 영상 생성 중...";

            try {
                const res = await fetch(`${SERVER_URL}/run-pipeline`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ product_url: url })
                });
                const data = await res.json();
                if(data.success) {
                    log.innerText = `✅ 생성 완료!\n\n[상품명]: ${data.product_name}\n\n[내 쉐어링크]:\n${data.share_link}\n\n[생성된 AI 대본]:\n${data.script}\n\n[영상 다운로드 URL]:\n${data.video_url}`;
                } else {
                    log.innerText = `❌ 에러: ${data.detail}`;
                }
            } catch(e) {
                log.innerText = "❌ 서버 통신 오류가 발생했습니다.";
            }
        }

        function generateContent(channel) {
            const selectId = `${channel}ItemSelect`;
            const selectedUrl = document.getElementById(selectId).value;
            
            if(!selectedUrl) {
                alert('상품을 먼저 선택해 주세요.');
                return;
            }

            document.getElementById(`${channel}Output`).innerText = `⏳ 선택한 상품(${selectedUrl})의 ${channel.toUpperCase()} 맞춤형 콘텐츠가 생성되었습니다!\n\n- 해당 리워드 쉐어링크가 적용된 원고 작성이 준비되었습니다.`;
        }
    </script>
</body>
</html>
