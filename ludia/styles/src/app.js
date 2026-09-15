import htmx from "htmx.org"
import { Application } from "@hotwired/stimulus"
import { definitions } from "stimulus:./controllers"

window.htmx = htmx

const app = Application.start()
app.load(definitions)
