/**
 * AuthoringRequestContext — the bar→editor carrier (Shell-2). Each submit gets a
 * fresh monotonic nonce (the rail delivers once per nonce); consume clears it.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect } from "vitest"

import { AuthoringRequestProvider, useAuthoringRequest } from "./AuthoringRequestContext"

function Harness() {
  const { request, submit, consume } = useAuthoringRequest()
  return (
    <div>
      <span data-testid="req">{request ? `${request.nl}#${request.nonce}` : "none"}</span>
      <button onClick={() => submit("draft a billing workflow")}>submit</button>
      <button onClick={() => submit("   ")}>submit-blank</button>
      <button onClick={consume}>consume</button>
    </div>
  )
}

function setup() {
  return render(
    <AuthoringRequestProvider>
      <Harness />
    </AuthoringRequestProvider>,
  )
}

describe("AuthoringRequestContext", () => {
  it("submit sets the request with a nonce; a second submit bumps the nonce", () => {
    setup()
    expect(screen.getByTestId("req")).toHaveTextContent("none")
    fireEvent.click(screen.getByText("submit"))
    const first = screen.getByTestId("req").textContent!
    expect(first).toMatch(/draft a billing workflow#1$/)
    fireEvent.click(screen.getByText("submit"))
    expect(screen.getByTestId("req")).toHaveTextContent(/#2$/)
  })

  it("consume clears the request", () => {
    setup()
    fireEvent.click(screen.getByText("submit"))
    expect(screen.getByTestId("req")).not.toHaveTextContent("none")
    fireEvent.click(screen.getByText("consume"))
    expect(screen.getByTestId("req")).toHaveTextContent("none")
  })

  it("a blank request is ignored (no nonce burned)", () => {
    setup()
    fireEvent.click(screen.getByText("submit-blank"))
    expect(screen.getByTestId("req")).toHaveTextContent("none")
    fireEvent.click(screen.getByText("submit"))
    expect(screen.getByTestId("req")).toHaveTextContent(/#1$/) // first real submit is nonce 1
  })
})
