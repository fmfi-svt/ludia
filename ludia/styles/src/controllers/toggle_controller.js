import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["element"]
  static classes = ["open", "closed"]

  open() {
    this.elementTarget.classList.add(...this.openClasses)
    this.elementTarget.classList.remove(...this.closedClasses)
  }

  close() {
    this.elementTarget.classList.add(...this.closedClasses)
    this.elementTarget.classList.remove(...this.openClasses)
  }

  isOpen() {
    for (const cls of this.openClasses) {
      if (this.elementTarget.classList.contains(cls)) {
        return true
      }
    }
    return false
  }

  toggle() {
    if (this.isOpen()) {
      this.close()
    } else {
      this.open()
    }
  }
}
