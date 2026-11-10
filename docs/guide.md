# Using SpaceTab · 사용 안내

## Favorites, pinned tabs and profiles

**Favorites / 즐겨찾기** are the large tiles at the top of the sidebar. With shared favorites
enabled, spaces in the same login profile refer to one live tab. Opening YouTube in another
space returns to the same page; it does not create another copy. Shared favorites are enabled
once by default; your later setting changes are respected.

**Pinned tabs / 고정 탭** and folders belong to the current space. They are useful for sites
you want in Work but not Play. Pinning two copies of a site is different from sharing one favorite.

**Profiles / 프로필** separate site login and storage. Two spaces using the same profile are
not isolated accounts. Shared favorites do not merge tabs across separate login profiles.

상단 즐겨찾기는 같은 로그인 프로필 안에서 실제 탭 하나를 공유합니다. 스페이스마다
따로 둘 사이트는 고정 탭에 두세요. 서로 다른 계정으로 로그인하려면 스페이스만 나누는
것으로는 부족하고, 로그인 프로필을 나눠야 합니다.

## Everyday controls

| Shortcut | Action / 동작 |
| --- | --- |
| `⌘T` | Command bar / 명령창 |
| `⌘L` | Edit address / 주소 수정 |
| `⌘S` | Show or hide sidebar / 사이드바 표시·숨김 |
| `⌃1`–`⌃9` | Switch space / 스페이스 전환 |
| `⌘D` | Pin or unpin / 고정·해제 |
| `⌘W` | Close tab / 탭 닫기 |
| `⌘⇧T` | Restore a closed tab / 닫은 탭 복구 |
| `⌘Q` | Quit application / 앱 종료 |

These are defaults and can be customized in Settings. Trackpad gestures depend on the input
device and settings; keyboard and sidebar switching remain available.

From 1.0.21, a one-time migration makes pages fill the window edge to edge and disables
dragging the whole window from webpage tops. Later preferences are preserved. You can
change **Pages fill the window edge to edge** in Settings → Tabs, or **Allow window dragging
from the top of webpages** in Settings → Advanced.

## Tidy Tabs

Tidy groups loose Today tabs using Apple's on-device Foundation Models. It needs macOS 26
or later, Apple Intelligence enabled and an available model. The button may be hidden when
the model is unavailable or there are no eligible tabs. macOS 14 alone does not provide Tidy.

Tidy는 macOS 26 이상에서 Apple Intelligence가 켜져 있고 모델을 사용할 수 있을 때
동작합니다. 조건을 충족하지 않거나 묶을 일반 탭이 없으면 버튼이 안 보일 수 있습니다.

## Dangerous site protection

Starting with 1.0.21, Settings → Privacy → **Dangerous site protection** accepts your own
Google Safe Browsing API key. There is no shared key in the download, and a saved key alone
does not mean Chromium's protection is active.

1. In your own [Google Cloud project](https://console.cloud.google.com/), enable the
   Safe Browsing API after reviewing its terms. Google limits Safe Browsing to
   [non-commercial use](https://developers.google.com/safe-browsing/reference).
2. Create a dedicated API key and restrict its allowed APIs to **Safe Browsing API**.
   Keep it private: do not put it in GitHub, a screenshot, a support issue or chat.
3. Save it in the app's Privacy settings, then restart SpaceTab. The app stores it in
   this Mac's Keychain, separately from the cookie/password encryption key.
4. **Verify key** checks Google's response to its public threat-test URLs. **Open status…**
   opens Chromium's internal status page; verify that the threat lists downloaded successfully.
   Google's official synthetic test pages can then confirm the browser warning. Do not
   bypass that warning or test with a real malicious site.

The first list download can take several minutes. This engine waits at least 24 hours
between successful list updates, so new threats can be missed. Ad blocking and encrypted
connections do not substitute for this protection. Google receives the network requests
needed by its protection service; the key is not sent to our GitHub repository.

1.0.21부터 개인 API 키를 이 Mac의 키체인에 저장할 수 있습니다. 저장 후 앱을 다시 열고,
키 확인·목록 다운로드·공식 테스트 경고를 각각 확인하세요. 다른 Mac에는 자동으로
설정되지 않으며, 광고 차단과 악성 사이트 보호는 별개입니다.

## Updates and the Mac password prompt

The application menu includes a manual update check. Connected copies also receive release
events that request a signed-feed check; periodic checks remain a fallback. Installation is
a user action by default. Updates verify both the feed and archive signatures.

**Workshop Storage** is a local Keychain item used for browser encryption. Its approval is
separate from GitHub access and update download. A transition from ad-hoc signing to the
persistent personal certificate can need one approval. Later builds keep the same signing
requirement; a locked Keychain or changed certificate can still prompt.

기본 설정은 자동 확인 후 설치 안내입니다. 암호를 묻는 Workshop Storage 창은 로컬
암호화 키 접근 승인으로, 업데이트 파일을 내려받기 위한 GitHub 암호가 아닙니다.

## Local recovery copies

Before an update proceeds, SpaceTab copies the old application and browsing profile to:

```text
~/Library/Application Support/Arc Workshop Backups/update-<build>-<id>/
  Arc Workshop.app/
  profile/
  snapshot-state
```

The profile copy is refreshed after Chromium shuts down. A finished snapshot has
`snapshot-state` set to `complete`. If preparation fails, the update stops. Snapshots are
local and are not a cloud backup or an automatic rollback mechanism.

To restore, quit SpaceTab completely. Preserve the current app and profile separately,
then restore **both** the app and `profile/` from the same complete snapshot. `profile/`
replaces `~/Library/Application Support/Arc Workshop`; the old app goes in Applications.
Keep the existing **Workshop Storage** Keychain item. The older app may need renewed access
approval. Restoring a profile without its encryption key may not recover saved logins.
An older browser can have known security bugs, so a rollback is a recovery measure.

복구할 때는 앱을 완전히 종료하고 현재 앱·프로필을 별도로 보관한 뒤, `complete`인
같은 복사본의 **앱과 프로필을 함께** 복원하세요. Workshop Storage 키체인은 지우지 마세요.
이전 앱이 키체인 접근을 다시 물을 수 있습니다. 사본은 전체 브라우징 데이터를 담을 수 있고
용량이 커질 수 있습니다. 필요한 복구 지점은 보관하고, 불필요한 사본은 직접 정리하세요.

## Reporting a problem

Use the issue forms with the app version, macOS version and a short reproduction. Do not
attach a full profile, cookie database, Keychain export or unredacted browsing log.
The version is visible in About SpaceTab and in the release's `release.json`.
