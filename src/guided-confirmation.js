export function guidedConfirmationPayload(item, response, selectedType) {
  const proposal = response.proposal;
  const active = item.dialogue_state?.active_proposal;
  if (proposal && active?.id === proposal.id
      && proposal.base_revision === item.revision && active.base_revision === item.revision
      && response.proposed_case_updates?.claim_type_id === selectedType) {
    return {proposal_id: proposal.id, expected_revision: item.revision, proposal_action: 'accept'};
  }
  return {
    claim_type_id: selectedType,
    conditions: structuredClone(response.proposed_case_updates?.conditions || {}),
    details: structuredClone(response.proposed_case_updates?.details || item.details || {}),
    expected_revision: item.revision,
  };
}
