document.addEventListener("DOMContentLoaded", function() {
    // Tìm dropdown Hành động và Nút thực thi
    const actionSelect = document.querySelector('.actions select[name="action"]');
    const actionBtn = document.querySelector('.actions button[type="submit"]');

    if (actionSelect && actionBtn) {
        // 1. Ép hệ thống mặc định chọn hành động "Xóa"
        actionSelect.value = 'delete_selected';
        
        // 2. Ẩn cái dòng "---------" rác đi cho chuyên nghiệp
        const emptyOption = actionSelect.querySelector('option[value=""]');
        if (emptyOption) emptyOption.style.display = 'none';

        // 3. Đổi tên nút "Đi đến" thành "Xác nhận xóa" và đổi sang MÀU ĐỎ cảnh báo
        actionBtn.innerHTML = '<i class="fas fa-trash"></i> Xác nhận xóa';
        actionBtn.style.backgroundColor = '#ef4444'; 
        actionBtn.style.borderColor = '#ef4444';

        // 4. Bắt sự kiện: Nếu người dùng chọn hành động khác (nếu có sau này) thì đổi lại màu nút
        actionSelect.addEventListener('change', function() {
            if (this.value === 'delete_selected') {
                actionBtn.innerHTML = '<i class="fas fa-trash"></i> Xác nhận xóa';
                actionBtn.style.backgroundColor = '#ef4444';
                actionBtn.style.borderColor = '#ef4444';
            } else {
                actionBtn.innerHTML = 'Thực hiện';
                actionBtn.style.backgroundColor = '#0ea5e9'; // Màu xanh da trời
                actionBtn.style.borderColor = '#0ea5e9';
            }
        });
    }

    function updateBulkActionMessage() {
        const actionsBar = document.querySelector('.actions');
        const resultList = document.querySelector('#result_list');
        if (!actionsBar || !resultList) return;

        const selectedCount = resultList.querySelectorAll('tbody input.action-select:checked').length;
        const pageCount = resultList.querySelectorAll('tbody input.action-select').length;
        const counter = actionsBar.querySelector('.action-counter');
        const question = actionsBar.querySelector('.question');
        const allSelected = actionsBar.querySelector('.all');
        const clear = actionsBar.querySelector('.clear');
        const totalCount = 0;
        const selectedAcross = false;
        const clearLink = null;

        [question, allSelected, clear].forEach(function(node) {
            if (node) node.remove();
        });
        return;

        if (counter) {
            const text = selectedCount
                ? `Đã chọn ${selectedCount}/${pageCount} sản phẩm`
                : 'Chưa chọn sản phẩm';
            if (counter.textContent !== text) counter.textContent = text;
        }

        if (question) {
            question.style.display = selectedCount === pageCount && totalCount > pageCount && !selectedAcross
                ? 'inline-flex'
                : 'none';
        }

        if (clear) {
            clear.style.display = selectedCount ? 'inline-flex' : 'none';
        }

        if (clearLink && clearLink.textContent !== 'Bỏ chọn') {
            clearLink.textContent = 'Bỏ chọn';
        }
    }

    updateBulkActionMessage();
    document.addEventListener('change', function(event) {
        if (event.target.matches('input.action-select, input#action-toggle')) {
            setTimeout(updateBulkActionMessage, 0);
        }
    });
    document.addEventListener('click', function(event) {
        if (event.target.closest('.actions .question a, .actions .clear a')) {
            setTimeout(updateBulkActionMessage, 0);
        }
    });

    const addButtons = document.querySelectorAll('a.btn.btn-success[href*="/add/"]');
        addButtons.forEach(function(btn) {
            if (btn.innerHTML.includes('Thêm vào')) {
                // Thay chữ "Thêm vào" bằng "Thêm mới", giữ nguyên tên danh mục/sản phẩm phía sau
                btn.innerHTML = btn.innerHTML.replace('Thêm vào', 'Thêm mới');
            }
        });

    // 6. MODAL IMPORT: FIX NGÔN NGỮ, NÚT HỦY VÀ LỖI SUBMIT
        const importBtn = document.querySelector('.object-tools a.import_link');
        if (importBtn) {
            importBtn.addEventListener('click', async function(e) {
                e.preventDefault(); 
                const importUrl = this.getAttribute('href');
                
                if (!document.getElementById('customImportModal')) {
                    const modalHtml = `
                    <div class="modal fade" id="customImportModal" tabindex="-1" role="dialog" aria-hidden="true">
                      <div class="modal-dialog modal-dialog-centered" role="document">
                        <div class="modal-content" style="border-radius: 16px; border: none; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
                          <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding: 15px 20px;">
                            <h5 class="modal-title" style="font-weight: 600; color: #334155; margin: 0;">Nhập dữ liệu từ tệp</h5>
                            <button type="button" class="close-modal-btn" style="background: transparent; border: none; font-size: 26px; color: #94a3b8; cursor: pointer;">&times;</button>
                          </div>
                          <div class="modal-body" id="importModalBody" style="padding: 20px;">
                                <div class="text-center"><i class="fas fa-spinner fa-spin fa-2x text-info"></i></div>
                          </div>
                        </div>
                      </div>
                    </div>`;
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                    document.querySelectorAll('.close-modal-btn').forEach(btn => btn.addEventListener('click', () => $('#customImportModal').modal('hide')));
                }
                
                $('#customImportModal').modal('show');

                try {
                    const response = await fetch(importUrl);
                    const htmlString = await response.text();
                    const doc = new DOMParser().parseFromString(htmlString, 'text/html');
                    const realForm = doc.querySelector('form[enctype="multipart/form-data"]');

                    if (realForm) {
                        // 1. Đảm bảo Form trỏ đúng đường dẫn action (để nó biết gửi file đi đâu)
                        realForm.setAttribute('action', importUrl);
                        realForm.setAttribute('method', 'POST');
                        realForm.setAttribute('enctype', 'multipart/form-data');

                        // 2. Việt hóa các nhãn (Giữ nguyên phần sếp đã làm)
                        realForm.querySelectorAll('label').forEach(label => {
                            if (label.innerText.includes('File to import')) label.innerText = 'Chọn tệp (Excel/CSV):';
                            if (label.innerText.includes('Format')) label.innerText = 'Định dạng tệp:';
                            label.style.display = 'block'; label.style.marginBottom = '8px'; label.style.fontWeight = '500';
                        });

                        // 3. XỬ LÝ NÚT BẤM - ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT
                        const originalSubmit = realForm.querySelector('input[type="submit"]') || realForm.querySelector('button[type="submit"]');
                        if (originalSubmit) originalSubmit.style.display = 'none'; // Ẩn nút gốc đi

                        const buttonContainer = document.createElement('div');
                        buttonContainer.style.display = 'flex'; buttonContainer.style.gap = '10px'; buttonContainer.style.marginTop = '15px';

                        const cancelBtn = document.createElement('button');
                        cancelBtn.type = 'button'; cancelBtn.className = 'btn btn-secondary w-50';
                        cancelBtn.innerText = 'Hủy bỏ'; cancelBtn.style.borderRadius = '8px';
                        cancelBtn.onclick = () => $('#customImportModal').modal('hide');

                        const submitBtn = document.createElement('button');
                        submitBtn.type = 'submit'; // <--- ĐỂ TYPE LÀ SUBMIT ĐỂ NÓ TỰ GỬI FORM
                        submitBtn.className = 'btn btn-primary w-50';
                        submitBtn.innerText = 'Tải lên & Xem trước'; 
                        submitBtn.style.borderRadius = '8px';
                        submitBtn.style.background = '#0ea5e9'; submitBtn.style.border = 'none';

                        buttonContainer.appendChild(cancelBtn);
                        buttonContainer.appendChild(submitBtn);
                        realForm.appendChild(buttonContainer);

                        // Xóa Loading và bơm Form vào
                        document.getElementById('importModalBody').innerHTML = '';
                        document.getElementById('importModalBody').appendChild(realForm);

                        // 4. FIX LỖI ĐÓNG MODAL: Khi bấm Submit, ta cho nó đợi 1 tí rồi mới chuyển trang
                        realForm.addEventListener('submit', function() {
                            console.log("Đang gửi dữ liệu...");
                            // Không dùng e.preventDefault() ở đây để trình duyệt tự chuyển trang
                        });
                    }
                } catch (e) { console.error(e); }
            });
        }

        // 7. BIẾN NÚT EXPORT THÀNH MODAL POPUP (CHỐT HẠ 100% SẠCH SẼ)
        const exportBtn = document.querySelector('.object-tools a.export_link');
        if (exportBtn) {
            exportBtn.addEventListener('click', async function(e) {
                e.preventDefault();
                const exportUrl = this.getAttribute('href');

                if (!document.getElementById('customExportModal')) {
                    const modalHtml = `
                    <div class="modal fade" id="customExportModal" tabindex="-1" role="dialog" aria-hidden="true">
                      <div class="modal-dialog modal-dialog-centered" role="document">
                        <div class="modal-content" style="border-radius: 16px; border: none; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
                          <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding: 15px 20px;">
                            <h5 class="modal-title" style="font-weight: 600; color: #334155; margin: 0;">Xuất dữ liệu (Export)</h5>
                            <button type="button" class="close-modal-btn" style="background: transparent; border: none; font-size: 26px; color: #94a3b8; cursor: pointer;">&times;</button>
                          </div>
                          <div class="modal-body" id="exportModalBody" style="padding: 20px;">
                                <div class="text-center"><i class="fas fa-spinner fa-spin fa-2x text-primary"></i></div>
                          </div>
                        </div>
                      </div>
                    </div>`;
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                    document.querySelectorAll('#customExportModal .close-modal-btn').forEach(btn => btn.addEventListener('click', () => $('#customExportModal').modal('hide')));
                }

                $('#customExportModal').modal('show');
                document.getElementById('exportModalBody').innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin fa-2x text-primary"></i></div>';

                try {
                    const response = await fetch(exportUrl);
                    let htmlString = await response.text();
                    
                    htmlString = htmlString.replace(/<div class="language-selection"[\s\S]*?<\/div>/g, '');
                    htmlString = htmlString.replace(/<ul class="language-chooser"[\s\S]*?<\/ul>/g, '');

                    const doc = new DOMParser().parseFromString(htmlString, 'text/html');
                    
                    let realForm = null;
                    doc.querySelectorAll('form').forEach(f => {
                        if (f.querySelector('input[type="checkbox"]')) {
                            realForm = f;
                        }
                    });

                    if (realForm) {
                        realForm.setAttribute('action', exportUrl);

                        // 1. CHÈN NÚT CHỌN TẤT CẢ / BỎ CHỌN TẤT CẢ TỰ TẠO
                        const actionCheckboxes = realForm.querySelector('.action-checkboxes') || document.createElement('div');
                        if (!realForm.querySelector('.action-checkboxes')) {
                            actionCheckboxes.className = 'action-checkboxes';
                            actionCheckboxes.style.marginBottom = '10px';
                            realForm.insertBefore(actionCheckboxes, realForm.firstChild);
                        }
                        actionCheckboxes.innerHTML = `
                            <a href="#" id="custom-select-all" style="color: #10b981; font-weight: 600; text-decoration: none; margin-right: 20px;"><i class="fas fa-check-square"></i> Chọn tất cả</a>
                            <a href="#" id="custom-clear-all" style="color: #ef4444; font-weight: 600; text-decoration: none;"><i class="fas fa-square"></i> Bỏ chọn tất cả</a>
                        `;

                        // --- MA THUẬT QUÉT SẠCH RÁC ---
                        realForm.querySelectorAll('label').forEach(label => {
                            if (label.textContent.toLowerCase().includes('select all')) {
                                const wrapperLi = label.closest('li') || label.parentElement;
                                if (wrapperLi) {
                                    wrapperLi.style.display = 'none'; // Ẩn khỏi màn hình
                                    wrapperLi.innerHTML = ''; // Xóa sạch ruột
                                }
                            }
                        });

                        const helpText = realForm.querySelector('p');
                        if (helpText && helpText.textContent.toLowerCase().includes('this exporter')) {
                            helpText.style.display = 'none';
                        }
                        // ------------------------------

                        // 2. CSS DANH SÁCH CHECKBOX
                        const ulBoxes = realForm.querySelector('ul');
                        if (ulBoxes) {
                            ulBoxes.style.cssText = 'padding: 0; margin-top: 15px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; background: #f8fafc;';
                            ulBoxes.querySelectorAll('li').forEach(li => {
                                // Nếu thẻ li đã bị xóa ruột ở trên thì bỏ qua
                                if (!li.innerHTML) return; 
                                
                                li.style.cssText = 'list-style: none; padding: 8px 0; display: inline-block; width: 48%; font-size: 14px;';
                                const label = li.querySelector('label');
                                if(label) label.style.cssText = 'font-weight: 500; color: #475569; display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0;';
                                const checkbox = li.querySelector('input[type="checkbox"]');
                                if (checkbox) checkbox.style.cssText = 'width: 16px; height: 16px; accent-color: #0ea5e9; cursor: pointer;';
                            });
                        }

                        // 3. XỬ LÝ FORMAT
                        const formatLabels = realForm.querySelectorAll('label');
                        formatLabels.forEach(lbl => {
                            if(lbl.innerText.toLowerCase().includes('format')) lbl.innerText = 'Định dạng tệp xuất:';
                        });
                        
                        const selectFormat = realForm.querySelector('select');
                        if (selectFormat) {
                            selectFormat.classList.add('form-control');
                            selectFormat.style.cssText = 'border-radius: 8px; margin-top: 8px; height: 42px; border: 1px solid #cbd5e1; width: 100%;';
                        }

                        // Ẩn nút submit mặc định
                        realForm.querySelectorAll('input[type="submit"], button[type="submit"]').forEach(btn => btn.style.display = 'none');

                        // 4. TẠO NÚT MỚI
                        const btnContainer = document.createElement('div');
                        btnContainer.style.cssText = 'display: flex; gap: 10px; margin-top: 25px; border-top: 1px solid #f1f5f9; padding-top: 15px;';

                        const cancelBtn = document.createElement('button');
                        cancelBtn.type = 'button'; cancelBtn.className = 'btn btn-secondary w-50';
                        cancelBtn.innerText = 'Hủy bỏ';
                        cancelBtn.onclick = () => $('#customExportModal').modal('hide');

                        const submitBtn = document.createElement('button');
                        submitBtn.type = 'submit'; submitBtn.className = 'btn btn-primary w-50';
                        submitBtn.innerText = 'Tải tệp xuống';
                        submitBtn.style.cssText = 'background: #0ea5e9; border: none; color: white; font-weight: 600; border-radius: 8px; padding: 10px;';

                        btnContainer.appendChild(cancelBtn);
                        btnContainer.appendChild(submitBtn);
                        realForm.appendChild(btnContainer);

                        document.getElementById('exportModalBody').innerHTML = '<p style="color: #64748b; margin-bottom: 15px; font-weight: 500;">Chọn các trường dữ liệu muốn xuất:</p>';
                        document.getElementById('exportModalBody').appendChild(realForm);

                        // 5. BẮT SỰ KIỆN CHỌN
                        document.getElementById('custom-select-all')?.addEventListener('click', (ev) => {
                            ev.preventDefault();
                            realForm.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
                        });
                        document.getElementById('custom-clear-all')?.addEventListener('click', (ev) => {
                            ev.preventDefault();
                            realForm.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                        });

                        // 6. CHỐT CHẶN BẢO VỆ
                        realForm.onsubmit = function(ev) {
                            const checkedBoxes = realForm.querySelectorAll('input[type="checkbox"]:checked');
                            if (checkedBoxes.length === 0) {
                                ev.preventDefault(); 
                                alert('Yêu cầu phải chọn ít nhất 1 trường dữ liệu (Id, Name...) thì mới xuất được tệp ạ!');
                                return false;
                            }
                            setTimeout(() => $('#customExportModal').modal('hide'), 1500);
                            return true;
                        };
                    }
                } catch (e) { 
                    document.getElementById('exportModalBody').innerHTML = '<p class="text-danger text-center mt-3">Lỗi kết nối máy chủ.</p>';
                }
            });
        }

        // 9. XỬ LÝ BẢNG KHI TRỐNG DỮ LIỆU (GIỮ LẠI TIÊU ĐỀ)
        const changelistForm = document.querySelector('#changelist-form');
        const resultList = document.querySelector('#result_list');
        
        // Đảm bảo chỉ chạy ở trang Danh sách (có form changelist)
        if (changelistForm && !resultList) {
            // Khi không có #result_list tức là bị Django ẩn đi do 0 kết quả
            // Ta tự tạo lại bảng với Header chuẩn của bảng Danh mục
            const emptyTableHtml = `
                <div class="card" style="border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: none;">
                    <div class="card-body table-responsive p-0">
                        <table class="table table-striped table-hover text-nowrap" style="margin: 0;">
                            <thead style="background-color: #f8fafc;">
                                <tr>
                                    <th style="width: 40px; padding: 15px;"><input type="checkbox" disabled></th>
                                    <th style="padding: 15px; font-weight: 600; color: #475569;">TÊN DANH MỤC</th>
                                    <th style="padding: 15px; font-weight: 600; color: #475569;">DANH MỤC CHA</th>
                                    <th style="padding: 15px; font-weight: 600; color: #475569;">TRẠNG THÁI</th>
                                    <th style="padding: 15px; font-weight: 600; color: #475569;">SỐ LƯỢNG SP</th>
                                    <th style="padding: 15px; font-weight: 600; color: #475569;">THAO TÁC</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colspan="6" class="text-center py-5">
                                        <div style="color: #64748b; padding: 30px 0;">
                                            <i class="fas fa-box-open fa-3x mb-3" style="color: #cbd5e1;"></i>
                                            <h5 style="font-weight: 600; color: #334155;">Không có dữ liệu phù hợp</h5>
                                            <p style="margin: 0; font-size: 14px;">Hệ thống không tìm thấy danh mục nào khớp với điều kiện lọc và tìm kiếm của bạn.</p>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            
            // Ẩn dòng chữ cảnh báo mặc định "0 Danh mục sản phẩm" của Django/Jazzmin đi cho đỡ rác
            const defaultWarning = document.querySelector('.alert-warning') || document.querySelector('.paginator');
            if (defaultWarning) defaultWarning.style.display = 'none';

            // Bơm cái bảng xịn xò này vào trong form
            changelistForm.insertAdjacentHTML('afterbegin', emptyTableHtml);

            const generatedEmptyTable = changelistForm.querySelector('.card table');
            if (generatedEmptyTable) {
                const generatedHead = generatedEmptyTable.querySelector('thead');
                const generatedCell = generatedEmptyTable.querySelector('tbody td[colspan]');
                if (generatedHead) generatedHead.remove();
                if (generatedCell) {
                    generatedCell.setAttribute('colspan', '1');
                    generatedCell.innerHTML = `
                        <div class="admin-empty-state">
                            <i class="fas fa-box-open"></i>
                            <h5>Khong co du lieu phu hop</h5>
                            <p>He thong khong tim thay ket qua nao khop voi dieu kien loc va tim kiem cua ban.</p>
                        </div>
                    `;
                }
            }
        }

        // 10. GIAO DIỆN BỘ LỌC NÂNG CAO (ADVANCED FILTERS)
        const searchContainer = document.querySelector('#changelist-search');
        if (searchContainer) {
            // Lấy tất cả các ô Combo Box bộ lọc
            const filterSelects = document.querySelectorAll('#changelist-search select, #change-list-filters select');
            
            if (filterSelects.length > 0) {
                // 1. Tạo nút Bộ lọc nâng cao
                const advancedBtn = document.createElement('button');
                advancedBtn.type = 'button';
                advancedBtn.id = 'custom-advanced-filter-btn';
                advancedBtn.innerHTML = '<i class="fas fa-sliders-h"></i> Bộ lọc nâng cao';
                
                // 2. Tạo Bảng chứa (Panel) để giấu các Select
                const panel = document.createElement('div');
                panel.id = 'custom-advanced-panel';
                panel.style.display = 'none'; // Mặc định ẩn
                
                // 3. Nhặt các Combo Box bỏ vào Panel
                filterSelects.forEach(select => {
                    // Cố gắng bốc cả cái thẻ <div> bọc ngoài của nó đi theo cho chuẩn layout
                    const wrapper = select.closest('.form-group') || select;
                    panel.appendChild(wrapper);
                });
                
                // 4. Cắm Nút bấm và Panel vào màn hình
                const searchBtn = searchContainer.querySelector('button[type="submit"]');
                if (searchBtn) {
                    searchBtn.parentNode.insertBefore(advancedBtn, searchBtn.nextSibling);
                }
                searchContainer.appendChild(panel);
                
                // 5. Code hiệu ứng xổ xuống / thu lại
                advancedBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (panel.style.display === 'none') {
                        panel.style.display = 'flex';
                        advancedBtn.classList.add('active');
                    } else {
                        panel.style.display = 'none';
                        advancedBtn.classList.remove('active');
                    }
                });

                // 6. Tự động mở Panel nếu sếp ĐANG LỌC dở dang
                let isFiltering = false;
                filterSelects.forEach(s => {
                    if (window.location.search.includes(s.name + '=')) isFiltering = true;
                });
                if (isFiltering) advancedBtn.click();
            }
        }
});
