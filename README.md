# Build NRO thành IPA chưa ký

Repo này chứa workflow và công cụ build, không chứa mã nguồn NRO.
Chạy thủ công trong GitHub Actions để nhận `GaMod-unsigned.ipa`, sau đó
tự ký bằng công cụ bạn sử dụng.

## Mã nguồn được lấy thế nào?

1. Máy macOS tạm của GitHub lấy công cụ từ repo BuildGithub này.
2. Token chỉ đọc giúp máy tải bản chụp NRO tại một commit đã xác định.
   Không chạy `git clone` với NRO, không lấy lịch sử Git.
3. Từ bản chụp đó, chỉ giải nén `Assets/`, `Packages/`, `ProjectSettings/`.
   Các workflow, công cụ CI và tệp khác ở gốc NRO không được giải nén.
4. Unity xuất Xcode; Xcode build ARM64 và đóng gói IPA chưa ký.
5. Chỉ tải `output/GaMod-unsigned.ipa` lên artifact, giữ 3 ngày.
   Mã nguồn, dự án Xcode và log chi tiết Xcode không được upload.
6. Dọn mã nguồn và kết quả trung gian sau job. Máy build do GitHub cung cấp
   cũng được hủy khi job kết thúc.

**Máy build vẫn phải nhận mã nguồn để biên dịch.** Tải bản chụp tránh clone
và lịch sử Git; thao tác này không đưa mã nguồn vào lịch sử repo BuildGithub.
Bản chụp tải qua mạng vẫn chứa các tệp của commit đó trước khi lọc giải nén.

Nên để cả **NRO và BuildGithub ở chế độ Private**. Nếu BuildGithub public,
người khác có thể xem log workflow; Unity có thể in tên tệp, lỗi biên dịch
hoặc nội dung do script của dự án ghi ra. Workflow không upload source,
nhưng không cam kết che mọi thông tin trong log của Unity.
Chỉ cấp quyền sửa workflow cho người bạn tin cậy vì workflow sử dụng secrets.

## Thiết lập một lần

1. Đưa các tệp của repo này lên repo BuildGithub trên GitHub.
   Workflow phải có trên **nhánh mặc định** để nút `Run workflow` xuất hiện.
2. Tạo fine-grained personal access token trong tài khoản sở hữu NRO:
   - Resource owner: `Mrk4tsu`.
   - Repository access: chọn riêng `NRO`.
   - Repository permissions → **Contents: Read-only**.
   - Chọn ngày hết hạn phù hợp.
3. Trong **BuildGithub → Settings → Secrets and variables → Actions**,
   thêm các repository secrets:

   | Secret | Nội dung |
   | --- | --- |
   | `NRO_READ_TOKEN` | Token chỉ đọc NRO vừa tạo |
   | `UNITY_EMAIL` | Email tài khoản Unity |
   | `UNITY_PASSWORD` | Mật khẩu tài khoản Unity |
   | `UNITY_LICENSE` | Toàn bộ nội dung `.ulf` nếu dùng Unity Personal |
   | `UNITY_SERIAL` | Serial nếu dùng Unity Pro; dùng thay `UNITY_LICENSE` |

   Không cần chứng chỉ Apple hoặc provisioning profile cho IPA chưa ký.
   Unity vẫn phải kích hoạt được giấy phép hợp lệ trên máy build.
   Xem [hướng dẫn kích hoạt GameCI](https://game.ci/docs/github/activation/).
   Secrets của NRO không tự chuyển sang BuildGithub; cần thiết lập ở BuildGithub.
   Không dán token hoặc mật khẩu vào YAML, mã nguồn hay chat.

## Chạy build và lấy IPA

1. Mở **BuildGithub → Actions → Build NRO unsigned IPA → Run workflow**.
2. `source_ref`: nhập branch, tag hoặc commit SHA của NRO, mặc định `main`.
   Workflow chốt SHA trước khi tải để tránh thay đổi mã giữa chừng.
   Chỉ build ref có mã bạn tin cậy.
3. Chờ job thành công; mở **Artifacts → NRO-iOS-unsigned-<SHA>**.
4. Giải nén artifact để lấy `GaMod-unsigned.ipa`, rồi ký trước khi cài lên iPhone.

Phiên bản Unity lấy từ `ProjectSettings/ProjectVersion.txt` của NRO
(hiện dự án dùng `2022.3.62f3`). Máy `macos-15-intel` cài Unity và module iOS
trong mỗi lượt chạy; không lưu cache dự án hay Xcode artifact.
Build dùng `Assets/Editor/IosCiBuild.cs` → `IosCiBuild.Export` đã có trong NRO.
Nhánh được chọn phải có tệp này cùng ít nhất một scene bật trong Build Settings.

Workflow chỉ chạy thủ công, không chạy từ pull request. Các lượt build
được xếp hàng để tránh kích hoạt nhiều phiên Unity cùng lúc.
Nếu Xcode lỗi, log chi tiết không được công bố; hãy chẩn đoán trong môi trường
riêng tư trước khi chủ động thêm bước xuất log. Giới hạn lưu artifact 3 ngày
còn phụ thuộc chính sách của repo/organization. Phút macOS có thể tính vào
hạn mức hoặc chi phí GitHub Actions của tài khoản.

Bản chụp không lấy nội dung submodule. Nếu NRO chuyển sang dùng Git LFS,
cần bật đưa LFS objects vào source archives; script dừng nếu gặp LFS pointer.

Tham khảo: [GitHub-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners),
[GitHub source archives](https://docs.github.com/en/rest/repos/contents#download-a-repository-archive-tar),
[GameCI Unity Builder](https://game.ci/docs/github/builder/).
