// Real macOS input for the carry profiler (scripts/carry/os.mjs): a trackpad two-finger swipe as scroll events
// with the gesture's phases (began, changed, ended) and its momentum (begin, continue, end), in pixels, one
// event per 60 Hz frame; or one key press. Posted at the HID level, so the browser sees what a trackpad sends.
// Needs Accessibility permission for the terminal that runs it.
//   swipe X Y DIR(+1 down, -1 up) PEAK HOLD DECAY      a swipe at screen point (X, Y)
//   swipe key CODE                                       one key press (115 Home, 119 End, 49 Space)
//   swipe --trusted                                      prints whether events may be posted
import Foundation
import CoreGraphics
import ApplicationServices
let a = CommandLine.arguments
if a.contains("--trusted") { print(AXIsProcessTrusted()); exit(0) }
let src = CGEventSource(stateID: .hidSystemState)
if a[1] == "key" {
  let code = CGKeyCode(Int(a[2])!)
  CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: true)?.post(tap: .cghidEventTap); usleep(40_000)
  CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: false)?.post(tap: .cghidEventTap)
  exit(0)
}
let x = Double(a[1])!, y = Double(a[2])!, dir = Double(a[3])!, peak = Double(a[4])!, hold = Int(a[5])!, decay = Double(a[6])!
CGWarpMouseCursorPosition(CGPoint(x: x, y: y))
usleep(30_000)
func post(_ dy: Double, phase: Int64, momentum: Int64) {
  guard let e = CGEvent(scrollWheelEvent2Source: src, units: .pixel, wheelCount: 1, wheel1: Int32((-dir * dy).rounded()), wheel2: 0, wheel3: 0) else { return }
  e.setIntegerValueField(.scrollWheelEventIsContinuous, value: 1)
  e.setIntegerValueField(.scrollWheelEventScrollPhase, value: phase)
  e.setIntegerValueField(.scrollWheelEventMomentumPhase, value: momentum)
  e.setDoubleValueField(.scrollWheelEventPointDeltaAxis1, value: -dir * dy)
  e.location = CGPoint(x: x, y: y)
  e.post(tap: .cghidEventTap)
  usleep(16_667)
}
// the fingers: a ramp to the peak and a hold (phase 1 began, 2 changed, 4 ended)
let ramp = [0.25, 0.5, 0.75, 1.0].map { $0 * peak }
for (i, d) in ramp.enumerated() { post(d, phase: i == 0 ? 1 : 2, momentum: 0) }
for _ in 0..<hold { post(peak, phase: 2, momentum: 0) }
post(0, phase: 4, momentum: 0)
// the momentum (1 begin, 2 continue, 3 end), falling by `decay` per frame
var v = peak * decay, first = true
while v >= 0.5 { post(v, phase: 0, momentum: first ? 1 : 2); first = false; v *= decay }
post(0, phase: 0, momentum: 3)
