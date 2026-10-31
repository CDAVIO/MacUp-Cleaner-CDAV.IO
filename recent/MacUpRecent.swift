// macup-recent — counts or clears the Apple menu's Recent Items
// (applications, documents, servers), the same list as Apple menu →
// Recent Items → Clear Menu. Files and apps themselves are never touched.
//
//   macup-recent count   → "apps docs servers"
//   macup-recent clear   → clears all three lists, then prints the new counts
//
// Uses Launch Services' shared file lists, so no Full Disk Access is needed.
import CoreServices
import Foundation

let kinds: [CFString] = [
    kLSSharedFileListRecentApplicationItems.takeUnretainedValue(),
    kLSSharedFileListRecentDocumentItems.takeUnretainedValue(),
    kLSSharedFileListRecentServerItems.takeUnretainedValue(),
]

func open(_ kind: CFString) -> LSSharedFileList? {
    LSSharedFileListCreate(nil, kind, nil)?.takeRetainedValue()
}

func count(_ list: LSSharedFileList) -> Int {
    var seed: UInt32 = 0
    return (LSSharedFileListCopySnapshot(list, &seed)?.takeRetainedValue() as? [AnyObject])?.count ?? 0
}

func counts() -> [Int] { kinds.map { k in open(k).map(count) ?? 0 } }

switch CommandLine.arguments.dropFirst().first {
case "count":
    print(counts().map(String.init).joined(separator: " "))
case "clear":
    var failed = false
    for k in kinds {
        guard let list = open(k) else { failed = true; continue }
        if count(list) > 0 && LSSharedFileListRemoveAllItems(list) != noErr { failed = true }
    }
    // The list daemon applies the change asynchronously.
    for _ in 0..<20 where counts().reduce(0, +) > 0 { Thread.sleep(forTimeInterval: 0.1) }
    print(counts().map(String.init).joined(separator: " "))
    exit(failed ? 1 : 0)
default:
    FileHandle.standardError.write("usage: macup-recent count|clear\n".data(using: .utf8)!)
    exit(2)
}
