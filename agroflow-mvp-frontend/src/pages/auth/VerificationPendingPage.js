import React from "react";

import { Link } from "react-router-dom";

export default function VerificationPendingPage() {
    return (
        <div className="container py-5">
            <div className="row justify-content-center">
                <div className="col-md-7">
                    <div className="card shadow-sm border-0">
                        <div className="card-body p-5">

                            <h2 className="fw-bold mb-3">
                                Verification Pending
                            </h2>

                            <p className="text-muted">
                                Your AgroFlow organization
                                registration has been submitted.
                            </p>

                            <p className="text-muted">
                                An AgroFlow administrator must
                                verify the organization before
                                restricted procurement operations
                                become available.
                            </p>

                            <div className="alert alert-warning">
                                Your account can be used to sign
                                in, but your organization is not
                                yet verified.
                            </div>

                            <Link
                                to="/login"
                                className="btn btn-dark"
                            >
                                Return to Login
                            </Link>

                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}