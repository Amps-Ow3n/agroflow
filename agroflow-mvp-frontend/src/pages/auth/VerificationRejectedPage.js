import React from "react";

import { Link } from "react-router-dom";

export default function VerificationRejectedPage() {
    return (
        <div className="container py-5">
            <div className="row justify-content-center">
                <div className="col-md-7">
                    <div className="card shadow-sm border-0">
                        <div className="card-body p-5">

                            <h2 className="fw-bold mb-3">
                                Verification Not Approved
                            </h2>

                            <p className="text-muted">
                                Your organization verification
                                request was not approved.
                            </p>

                            <div className="alert alert-danger">
                                Please contact the AgroFlow
                                administrator for clarification
                                or resubmission instructions.
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