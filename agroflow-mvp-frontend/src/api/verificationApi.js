import client from "./client";


export async function getPendingVerifications() {
    const response = await client.get(
        "/organizations/verifications/pending"
    );

    return response.data;
}


export async function getOrganizationVerification(
    organizationId
) {
    const response = await client.get(
        `/organizations/${organizationId}/verification`
    );

    return response.data;
}


export async function decideOrganizationVerification(
    organizationId,
    payload
) {
    const response = await client.post(
        `/organizations/${organizationId}/verification/decision`,
        payload
    );

    return response.data;
}