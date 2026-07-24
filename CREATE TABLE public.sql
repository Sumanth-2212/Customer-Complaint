CREATE TABLE public.complaints (
	id serial4 NOT NULL,
	complaint_source varchar(120) NULL,
	customer_name varchar(240) NULL,
	product_name varchar(240) NULL,
	product_strength varchar(120) NULL,
	batch_number varchar(120) NULL,
	manufacturing_date varchar(40) NULL,
	expiry_date varchar(40) NULL,
	quantity_affected varchar(60) NULL,
	complaint_type varchar(120) NULL,
	complaint_date varchar(40) NULL,
	complaint_description text NULL,
	initial_severity varchar(40) NULL,
	priority varchar(40) NULL,
	status varchar(40) NOT NULL,
	created_at timestamptz NOT NULL,
	CONSTRAINT complaints_pkey PRIMARY KEY (id)
)