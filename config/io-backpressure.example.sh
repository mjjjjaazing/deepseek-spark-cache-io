# Add to your configured MiaAI scripts/local.sh after rebuilding with the patch.
# This is the I/O extension runtime switch. It is off when unset or not exactly "1".
export TF_SPILL_IO_BACKPRESSURE=1

# To disable the policy, set it to 0 and restart through your existing supervisor.
# Do not override engine/cache compatibility fingerprints.
