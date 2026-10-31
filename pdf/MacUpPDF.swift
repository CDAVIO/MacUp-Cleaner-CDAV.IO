// macup-pdf — turns MacUp's HTML health report into an A4 PDF using the
// WebKit that ships with macOS. No network access, no dependencies.
//
//   macup-pdf report.html report.pdf
//
// The report is laid out as fixed 794×1123 px pages (A4 at 96 dpi); each page
// is captured separately and the pages are joined with PDFKit.
// Build: bash pdf/build.sh  (universal binary → bin/macup-pdf)

import AppKit
import PDFKit
import WebKit

let pageWidth: CGFloat = 794
let pageHeight: CGFloat = 1123

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("macup-pdf: \(message)\n".utf8))
    exit(1)
}

let args = CommandLine.arguments
guard args.count == 3 else { fail("usage: macup-pdf input.html output.pdf") }
let input = URL(fileURLWithPath: args[1]).standardizedFileURL
let output = URL(fileURLWithPath: args[2]).standardizedFileURL
guard FileManager.default.fileExists(atPath: input.path) else { fail("input not found") }

final class Renderer: NSObject, WKNavigationDelegate {
    let webView: WKWebView
    var document = PDFDocument()

    override init() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: pageWidth, height: pageHeight), configuration: config)
        super.init()
        webView.navigationDelegate = self
    }

    func start() {
        // Only the report's own folder is readable; nothing is fetched online.
        webView.loadFileURL(input, allowingReadAccessTo: input.deletingLastPathComponent())
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(action.request.url?.isFileURL == true ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript("document.querySelectorAll('.page').length") { result, _ in
            let count = max(1, (result as? NSNumber)?.intValue ?? 1)
            // Make the view as tall as all pages so every page can be captured.
            webView.setFrameSize(NSSize(width: pageWidth, height: pageHeight * CGFloat(count)))
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { self.capture(page: 0, of: count) }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription) }

    func capture(page: Int, of count: Int) {
        guard page < count else { return finish() }
        let config = WKPDFConfiguration()
        config.rect = CGRect(x: 0, y: CGFloat(page) * pageHeight, width: pageWidth, height: pageHeight)
        webView.createPDF(configuration: config) { result in
            switch result {
            case .success(let data):
                guard let pdf = PDFDocument(data: data), let first = pdf.page(at: 0) else { fail("empty page \(page + 1)") }
                self.document.insert(first, at: self.document.pageCount)
                self.capture(page: page + 1, of: count)
            case .failure(let error):
                fail(error.localizedDescription)
            }
        }
    }

    func finish() {
        document.documentAttributes = [
            PDFDocumentAttribute.titleAttribute: "MacUp — Mac Health Report",
            PDFDocumentAttribute.creatorAttribute: "MacUp (macup.cdav.io)",
        ]
        guard document.write(to: output) else { fail("could not write \(output.path)") }
        exit(0)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let renderer = Renderer()
renderer.start()
DispatchQueue.main.asyncAfter(deadline: .now() + 45) { fail("timed out") }
app.run()
