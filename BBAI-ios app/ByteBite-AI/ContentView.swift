//
//  ContentView.swift
//  ByteBite-AI
//
//  Created by Andrea Filiberto Lucas on 14/11/2024.
//

import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var showError: Bool

    class Coordinator: NSObject, WKNavigationDelegate, UIScrollViewDelegate {
        var parent: WebView
        private var didTriggerRefresh = false

        init(parent: WebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
            didTriggerRefresh = false
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.showError = true
            didTriggerRefresh = false
        }

        func scrollViewDidScroll(_ scrollView: UIScrollView) {
            if scrollView.contentOffset.y < -150 {
                didTriggerRefresh = true
            }
        }

        func scrollViewDidEndDragging(_ scrollView: UIScrollView, willDecelerate decelerate: Bool) {
            if didTriggerRefresh && !parent.isLoading {
                parent.refreshWebView(scrollView)
            }
            didTriggerRefresh = false
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.navigationDelegate = context.coordinator
        webView.scrollView.delegate = context.coordinator
        webView.load(URLRequest(url: url))
        
        let swipeLeft = UISwipeGestureRecognizer(target: context.coordinator, action: #selector(context.coordinator.handleSwipeLeft))
        swipeLeft.direction = .left
        webView.addGestureRecognizer(swipeLeft)

        let swipeRight = UISwipeGestureRecognizer(target: context.coordinator, action: #selector(context.coordinator.handleSwipeRight))
        swipeRight.direction = .right
        webView.addGestureRecognizer(swipeRight)

        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        // No update required for static URL
    }

    private func refreshWebView(_ scrollView: UIScrollView) {
        if !isLoading {
            isLoading = true
            scrollView.setContentOffset(.zero, animated: true)
            if let webView = scrollView.superview as? WKWebView {
                webView.reload()
            }
        }
    }
}

extension WebView.Coordinator {
    @objc func handleSwipeLeft(_ gesture: UISwipeGestureRecognizer) {
        if let webView = gesture.view as? WKWebView, webView.canGoForward {
            webView.goForward()
        }
    }

    @objc func handleSwipeRight(_ gesture: UISwipeGestureRecognizer) {
        if let webView = gesture.view as? WKWebView, webView.canGoBack {
            webView.goBack()
        }
    }
}

struct ContentView: View {
    @State private var isLoading = false
    @State private var showError = false
    @State private var showUrlInput = true
    @State private var userUrl: String = ""

    var body: some View {
        VStack(spacing: 0) {
            if showUrlInput {
                VStack {
                    Text("[DEV MODE]")
                        .font(.headline)
                        .padding()
                    
                    TextField("http://XXX.XXX.XX.XXX:XXXX", text: $userUrl)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .padding()

                    Button(action: {
                        if let url = URL(string: userUrl), url.scheme == "http" || url.scheme == "https" {
                            showUrlInput = false
                        } else {
                            showError = true
                        }
                    }) {
                        Text("Launch")
                            .fontWeight(.bold)
                            .padding()
                            .foregroundColor(.white)
                            .background(Color.blue)
                            .cornerRadius(8)
                    }
                }
                .padding()
                .background(Color.white)
            } else {
                ZStack {
                    WebView(url: URL(string: userUrl)!, isLoading: $isLoading, showError: $showError)
                        .background(Color.black)

                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle())
                            .scaleEffect(1.5)
                    }
                }
            }
        }
        .background(Color.black)
        .edgesIgnoringSafeArea(.bottom)
        .alert(isPresented: $showError) {
            Alert(
                title: Text("Invalid URL"),
                message: Text("Please enter a valid URL."),
                dismissButton: .default(Text("OK"))
            )
        }
    }
}

#Preview {
    ContentView()
}
