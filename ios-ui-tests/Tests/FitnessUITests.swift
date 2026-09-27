import XCTest

final class FitnessUITests: XCTestCase {
    let app = XCUIApplication(bundleIdentifier: "com.example.fitness.iosprobe")

    override func setUpWithError() throws {
        continueAfterFailure = false
        app.launch()
        XCTAssertTrue(button("训练").waitForExistence(timeout: 45), app.debugDescription)
    }

    override func tearDownWithError() throws {
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = "final-screen"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = "accessibility-hierarchy"
        hierarchy.lifetime = .keepAlways
        add(hierarchy)
        app.terminate()
    }

    func button(_ title: String) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label == %@ OR label BEGINSWITH %@", title, title + "\n")).firstMatch
    }
    func tap(_ title: String) {
        let element = button(title)
        XCTAssertTrue(element.waitForExistence(timeout: 15), "Missing button \(title): \(app.debugDescription)")
        for _ in 0..<4 {
            if element.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(element.isHittable, "Button obscured: \(title)")
        element.tap()
    }
    func field(_ title: String) -> XCUIElement {
        app.textFields.matching(NSPredicate(format: "label CONTAINS %@ OR placeholderValue CONTAINS %@", title, title)).firstMatch
    }
    func fill(_ title: String, _ value: String) {
        let element = field(title)
        XCTAssertTrue(element.waitForExistence(timeout: 15), "Missing field \(title): \(app.debugDescription)")
        element.tap()
        // iOS shows QuickPath onboarding the first time its text keyboard opens.
        let introduction = app.otherElements["UIContinuousPathIntroductionView"]
        if introduction.waitForExistence(timeout: 2) {
            introduction.buttons["Continue"].tap()
        }
        if let current = element.value as? String, !current.isEmpty, current != title {
            element.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: current.count))
        }
        if !value.isEmpty { element.typeText(value) }
        dismissKeyboard()
    }
    func expectText(_ text: String) {
        let element = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
        XCTAssertTrue(element.waitForExistence(timeout: 15), "Missing text \(text): \(app.debugDescription)")
    }
    func capture(_ name: String) {
        let item = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        item.name = name; item.lifetime = .keepAlways; add(item)
    }
    func dismissKeyboard() {
        let introduction = app.otherElements["UIContinuousPathIntroductionView"]
        if introduction.exists { introduction.buttons["Continue"].tap() }
        let done = app.keyboards.buttons.matching(NSPredicate(format: "label IN %@", ["Done", "done", "Return", "return", "完成", "换行"])).firstMatch
        XCTAssertTrue(done.waitForExistence(timeout: 10), "No keyboard submit key: \(app.debugDescription)")
        done.tap()
        let hidden = NSPredicate { _, _ in !self.app.keyboards.firstMatch.exists }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: hidden, object: nil)], timeout: 10), .completed)
    }
    func cancelPicker(exporting: Bool = false) {
        // The export picker can automatically enter On My iPhone. Go back to
        // Browse before cancelling: the folder page has Save, not a Cancel button.
        let cancel = app.buttons.matching(NSPredicate(format: "label IN %@", ["Cancel", "取消"])).firstMatch
        let back = app.buttons["Browse"]
        if exporting { XCTAssertTrue(app.buttons["Save"].waitForExistence(timeout: 30), app.debugDescription) }
        let ready = NSPredicate { _, _ in (cancel.exists && cancel.isHittable) || (back.exists && back.isHittable) }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: ready, object: nil)], timeout: 30), .completed)
        if back.exists && back.isHittable { back.tap() }
        let visible = NSPredicate { _, _ in cancel.exists && cancel.isHittable }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: visible, object: nil)], timeout: 15), .completed)
        cancel.tap()
        let dismissed = NSPredicate { _, _ in !cancel.exists && self.button("恢复备份").isHittable }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: dismissed, object: nil)], timeout: 15), .completed)
    }

    func testTrainingWeightAndRecovery() throws {
        fill("输入今日体重", "75.2")
        tap("训练")
        tap("开始训练")
        XCTAssertFalse(button("继承数据").isEnabled)
        XCTAssertFalse(button("下一组数").isEnabled)
        fill("动作名称", "Squat")
        fill("次数", "10")
        XCTAssertFalse(button("下一组数").isEnabled)
        fill("重量", "40")
        XCTAssertTrue(button("下一组数").isEnabled)
        tap("下一组数")
        expectText("第 2 组")
        tap("继承数据")
        XCTAssertTrue((field("次数").value as? String ?? "").contains("10"))
        XCTAssertTrue((field("重量").value as? String ?? "").contains("40"))
        fill("次数", "8")
        fill("重量", "")
        tap("下一动作")
        expectText("是否切换动作？")
        tap("取消")
        XCTAssertTrue((field("次数").value as? String ?? "").contains("8"))
        tap("下一动作")
        tap("确认")
        expectText("第 1 组")
        XCTAssertFalse(button("继承数据").isEnabled)
        fill("动作名称", "Row")
        fill("重量", "20")
        tap("暂停")
        capture("paused-draft")
        app.terminate()
        app.launch()
        tap("训练")
        tap("继续训练")
        XCTAssertTrue((field("动作名称").value as? String ?? "").contains("Row"))
        XCTAssertTrue((field("重量").value as? String ?? "").contains("20"))
        XCTAssertTrue(button("继续").exists)
        tap("继续")
        let timer = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "本组时长")).firstMatch
        let before = timer.label
        let advancing = NSPredicate { _, _ in timer.label != before }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: advancing, object: nil)], timeout: 5), .completed)
        tap("暂停")
        tap("结束训练")
        expectText("是否结束训练？")
        tap("确认")
        expectText("10次 × 40kg")
        expectText("8次 × —")
        expectText("— × 20kg")
        capture("recorded-partial-sets")
        // The weight is saved for today and survives restart/navigation.
        app.swipeUp()
        XCTAssertTrue((field("输入今日体重").value as? String ?? "").contains("75.2"))
        capture("saved-weight")
    }

    func testBackupPickersCanOpenAndCancel() throws {
        tap("我的")
        tap("导出备份")
        cancelPicker(exporting: true)
        expectText("已取消导出")
        tap("恢复备份")
        cancelPicker()
        tap("记录")
        expectText("本周训练次数")
    }
}
