import { configureStore, createSlice } from "@reduxjs/toolkit";

const emptyForm = {
  complaint_source: "",
  customer_name: "",
  product_name: "",
  product_strength: "",
  batch_number: "",
  manufacturing_date: "",
  expiry_date: "",
  quantity_affected: "",
  complaint_type: "",
  complaint_date: "",
  complaint_description: "",
  initial_severity: "",
  priority: "",
};

const complaintSlice = createSlice({
  name: "complaint",
  initialState: {
    form: { ...emptyForm },
    savedId: null,
    extraction: {
      status: "idle", // idle | uploading | extracting | done | error
      progress: 0,
      message: "",
    },
    chat: [
      {
        role: "assistant",
        text:
          "Upload a complaint document or paste text above. I will automatically extract the details and populate the form for you.",
      },
    ],
  },
  reducers: {
    setField(state, action) {
      const { key, value } = action.payload;
      state.form[key] = value;
    },
    resetForm(state) {
      state.form = { ...emptyForm };
      state.savedId = null;
      state.extraction = { status: "idle", progress: 0, message: "" };
    },
    populateForm(state, action) {
      state.form = { ...state.form, ...action.payload };
    },
    setSavedId(state, action) {
      state.savedId = action.payload;
    },
    setExtraction(state, action) {
      state.extraction = { ...state.extraction, ...action.payload };
    },
    addChat(state, action) {
      state.chat.push(action.payload);
    },
  },
});

export const {
  setField,
  resetForm,
  populateForm,
  setSavedId,
  setExtraction,
  addChat,
} = complaintSlice.actions;

export const store = configureStore({
  reducer: { complaint: complaintSlice.reducer },
});

export const emptyFormState = emptyForm;
